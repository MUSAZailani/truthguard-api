import os
import io
import asyncio
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

# ===== CONFIG =====
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "gsk_your_key_here") # Put your key or use.env
MODEL = "llama-3.1-8b-instant"
CREDITS_PER_50_ROWS = 1
CHUNK_SIZE = 50 # <-- NEW: Process 50 rows at a time to avoid 429
RETRY_DELAY = 2 # <-- NEW: Wait 2s between chunks

client = Groq(api_key=GROQ_API_KEY)
app = FastAPI(title="TruthGuard AI v4.3")
templates = Jinja2Templates(directory="templates")

# In-memory credits. Replace with DB later
user_credits = {"free_user": 500}

# ===== PROMPT =====
SYSTEM_PROMPT = """
You are TruthGuard AI. Your job is to clean text and fact-check it.
For each input line, return JSON with 4 fields:
"original", "cleaned", "verdict", "explanation"
Verdict must be one of: True, False, Partially True
Return ONLY a JSON array. No extra text.
"""

# ===== CORE AI FUNCTION WITH CHUNKING =====
async def process_chunk(chunk: list) -> list:
    """Process 50 rows at a time"""
    data_text = "\n".join([f"{i+1}. {row}" for i, row in enumerate(chunk)])
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Process these lines:\n{data_text}"}
    ]
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"} # Forces JSON
        )
        content = response.choices[0].message.content
        # Groq sometimes wraps in ```json
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        return eval(content) if isinstance(eval(content), list) else [eval(content)]
    except RateLimitError:
        await asyncio.sleep(RETRY_DELAY)
        return await process_chunk(chunk) # retry once
    except Exception as e:
        # If AI fails, return original with error
        return [{"original": r, "cleaned": r, "verdict": "Error", "explanation": str(e)} for r in chunk]

async def clean_and_verify_all(data: list) -> list:
    """NEW: Split into chunks and process safely"""
    results = []
    for i in range(0, len(data), CHUNK_SIZE):
        chunk = data[i:i + CHUNK_SIZE]
        chunk_result = await process_chunk(chunk)
        results.extend(chunk_result)
        await asyncio.sleep(RETRY_DELAY) # <-- NEW: Wait between chunks to avoid 429
    return results

# ===== ROUTES - SAME AS YOURS, JUST UPDATED FUNCTION CALL =====
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    credits = user_credits.get("free_user", 0)
    return templates.TemplateResponse("index.html", {"request": request, "credits": credits})

@app.post("/process")
async def process_data(request: Request, data: str = Form(None), file: UploadFile = File(None)):
    credits = user_credits.get("free_user", 0)

    # 1. Get data
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

    # 2. Check credits
    credits_needed = (len(data_list) // 50 + 1) * CREDITS_PER_50_ROWS
    if credits < credits_needed:
        return JSONResponse({"error": f"Not enough credits. Need {credits_needed}, have {credits}"}, status_code=402)

    # 3. Process with new chunking
    results = await clean_and_verify_all(data_list)

    # 4. Deduct credits
    user_credits["free_user"] -= credits_needed

    # 5. Return same format as before
    df_out = pd.DataFrame(results)
    csv = df_out.to_csv(index=False)
    return StreamingResponse(io.StringIO(csv), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=truthguard_cleaned.csv"})

@app.post("/export_pdf")
async def export_pdf(request: Request, data: str = Form(...)):
    import json
    results = json.loads(data)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph("TruthGuard AI Audit Report", styles['Title']), Spacer(1, 12)]

    table_data = [["Original", "Cleaned", "Verdict", "Explanation"]]
    for r in results:
        table_data.append([r['original'], r['cleaned'], r['verdict'], r['explanation']])

    t = Table(table_data, colWidths=[100, 100, 70, 200])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=TruthGuard_Report.pdf"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)