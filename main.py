import os
import io
import asyncio
import gc
import traceback
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from groq import Groq, RateLimitError
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import uvicorn

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise Exception("GROQ_API_KEY environment variable not set!") # <-- This will tell us

MODEL = "llama-3.1-8b-instant"
CREDITS_PER_50_ROWS = 1
CHUNK_SIZE = 50
RETRY_DELAY = 2

client = Groq(api_key=GROQ_API_KEY)
app = FastAPI(title="TruthGuard AI v4.4")
templates = Jinja2Templates(directory="templates")
user_credits = {"free_user": 500}

SYSTEM_PROMPT = """You are TruthGuard AI. Your job is to clean text and fact-check it.
For each input line, return JSON with 4 fields:
"original", "cleaned", "verdict", "explanation"
Verdict must be one of: True, False, Partially True
Return ONLY a JSON array. No extra text.
"""

async def process_chunk(chunk: list) -> list:
    data_text = "\n".join([f"{i+1}. {row}" for i, row in enumerate(chunk)])
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Process these lines:\n{data_text}"}
    ]
    try:
        response = client.chat.completions.create(model=MODEL, messages=messages, temperature=0)
        content = response.choices[0].message.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        return eval(content) if isinstance(eval(content), list) else [eval(content)]
    except RateLimitError:
        await asyncio.sleep(RETRY_DELAY)
        return await process_chunk(chunk)
    except Exception as e:
        return [{"original": r, "cleaned": r, "verdict": "Error", "explanation": str(e)} for r in chunk]

async def clean_and_verify_all(data: list) -> list:
    results = []
    for i in range(0, len(data), CHUNK_SIZE):
        chunk = data[i:i + CHUNK_SIZE]
        chunk_result = await process_chunk(chunk)
        results.extend(chunk_result)
        await asyncio.sleep(RETRY_DELAY)
    return results

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    try:
        credits = user_credits.get("free_user", 0)
        return templates.TemplateResponse("index.html", {"request": request, "credits": credits})
    except Exception as e:
        return HTMLResponse(f"Template Error: {str(e)}")

@app.post("/process")
async def process_data(request: Request, data: str = Form(None), file: UploadFile = File(None)):
    try:
        credits = user_credits.get("free_user", 0)
        if file:
            content = await file.read()
            if file.filename.endswith('.csv'):
                df = pd.read_csv(io.StringIO(content.decode('utf-8')))
                data_list = df.iloc[:, 0].dropna().astype(str).tolist()
            else:
                data_list = content.decode('utf-8').splitlines()
        elif data:
            data_list = data.splitlines()
        else:
            raise HTTPException(status_code=400, detail="No data provided")

        data_list = [d.strip() for d in data_list if d.strip()]
        credits_needed = (len(data_list) // 50 + 1) * CREDITS_PER_50_ROWS
        if credits < credits_needed:
            return JSONResponse({"error": f"Not enough credits. Need {credits_needed}, have {credits}"}, status_code=402)

        results = await clean_and_verify_all(data_list)
        user_credits["free_user"] -= credits_needed
        df_out = pd.DataFrame(results)
        csv = df_out.to_csv(index=False)
        gc.collect()
        return StreamingResponse(io.StringIO(csv), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=truthguard_cleaned.csv"})
    except Exception as e:
        print(traceback.format_exc()) # <-- This prints full error to Railway logs
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)