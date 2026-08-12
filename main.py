import os
import io
import asyncio
import gc
import json
import traceback
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from groq import Groq, RateLimitError
import uvicorn

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise Exception("GROQ_API_KEY environment variable not set!")

MODEL = "llama-3.1-8b-instant"
CREDITS_PER_50_ROWS = 1
CHUNK_SIZE = 50
RETRY_DELAY = 2

client = Groq(api_key=GROQ_API_KEY)
app = FastAPI(title="TruthGuard AI v5.0")
user_credits = {"free_user": 500}

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
  <title>TruthGuard AI Pro</title>
  <style>
    body { font-family: Arial; max-width: 900px; margin: 40px auto; padding: 20px; background:#0f172a; color:white; }
    textarea { width: 100%; height: 300px; padding: 10px; background:#1e293b; color:white; border:1px solid #334155; }
    button { padding: 12px 24px; margin: 5px; background: #2563eb; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight:bold; }
    button:hover { background: #1d4ed8; }
   .credits { font-size: 22px; font-weight: bold; color: #22c55e; }
  </style>
</head>
<body>
  <h1>🛡️ TruthGuard AI Pro v5.0</h1>
  <p class="credits">Your Credits: {credits}</p>

  <form action="/process" method="post" enctype="multipart/form-data">
    <h3>Option 1: Paste Your Data</h3>
    <textarea name="data" id="data" placeholder="Paste 1 row per line..."></textarea>
    <br>
    <button type="button" onclick="generateMessyData(5000)">⚡ Generate 5000 Messy Rows</button>
    <button type="button" onclick="generateMessyData(20000)">🔥 Generate 20,000 Rows</button>
    <h3>Option 2: Upload File</h3>
    <input type="file" name="file" accept=".csv,.txt">
    <br><br>
    <button type="submit">Clean My Data</button>
  </form>
  <script>
  function generateMessyData(n){
    const typos = ["teh", "recieve", "adress", "iphnoe 15", "samsng s24"];
    const falseClaims = ["Nigeria capital is Lagos", "Water boils at 50c", "The earth is flat"];
    const products = ["iPhone", "Laptop", "Shoe", "Bag"];
    let text = "";
    for(let i=0; i<n; i++){
      let rand = Math.random();
      if(rand < 0.5){ text += typos[Math.floor(Math.random()*typos.length)] + " " + products[Math.floor(Math.random()*products.length)] + "\n"; }
      else if(rand < 0.8){ text += falseClaims[Math.floor(Math.random()*falseClaims.length)] + "\n"; }
      else { text += "Brand new " + products[Math.floor(Math.random()*products.length)] + " for sale\n"; }
    }
    document.getElementById("data").value = text;
    alert(n.toLocaleString() + " rows generated!");
  }
  </script>
</body>
</html>
"""

SYSTEM_PROMPT = """You are TruthGuard AI. Your job is to clean text and fact-check it.
For each input line, return a JSON array of objects. Each object has 4 keys:
"original", "cleaned", "verdict", "explanation"
Verdict must be one of: True, False, Partially True
Return ONLY the JSON array. No extra text, no markdown.
"""

async def process_chunk(chunk: list) -> list:
    data_text = "\n".join([f"{i+1}. {row}" for i, row in enumerate(chunk)])
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": f"Process these lines:\n{data_text}"}]
    try:
        response = client.chat.completions.create(model=MODEL, messages=messages, temperature=0, response_format={"type": "json_object"})
        content = response.choices[0].message.content.strip().replace("```json", "").replace("```", "")
        data = json.loads(content)
        if isinstance(data, dict) and "data" in data: data = data["data"]
        return data if isinstance(data, list) else [data]
    except RateLimitError:
        await asyncio.sleep(RETRY_DELAY)
        return await process_chunk(chunk)
    except Exception as e:
        return [{"original": r, "cleaned": r, "verdict": "Error", "explanation": str(e)} for r in chunk]

async def clean_and_verify_all(data: list) -> list:
    results = []
    for i in range(0, len(data), CHUNK_SIZE):
        results.extend(await process_chunk(data[i:i + CHUNK_SIZE]))
        await asyncio.sleep(RETRY_DELAY)
    return results

@app.get("/", response_class=HTMLResponse)
async def home():
    credits = user_credits.get("free_user", 500)
    if isinstance(credits, dict): credits = 500
    return HTMLResponse(HTML_PAGE.format(credits=int(credits)))

@app.post("/process")
async def process_data(data: str = Form(None), file: UploadFile = File(None)):
    try:
        credits = user_credits.get("free_user", 500)
        if isinstance(credits, dict): credits = 500
        if file:
            content = await file.read()
            df = pd.read_csv(io.StringIO(content.decode('utf-8'))) if file.filename.endswith('.csv') else None
            data_list = df.iloc[:, 0].dropna().astype(str).tolist() if df is not None else content.decode('utf-8').splitlines()
        elif data: data_list = data.splitlines()
        else: raise HTTPException(status_code=400, detail="No data provided")

        data_list = [d.strip() for d in data_list if d.strip()]
        credits_needed = (len(data_list) // 50 + 1) * CREDITS_PER_50_ROWS
        if credits < credits_needed: return JSONResponse({"error": f"Not enough credits. Need {credits_needed}, have {credits}"}, status_code=402)

        results = await clean_and_verify_all(data_list)
        user_credits["free_user"] = int(credits) - credits_needed
        df_out = pd.DataFrame(results)
        csv = df_out.to_csv(index=False)
        gc.collect()
        return StreamingResponse(io.StringIO(csv), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=truthguard_cleaned.csv"})
    except Exception as e:
        print(traceback.format_exc())
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=8000)