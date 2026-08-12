import os
import io
import asyncio
import gc
import json
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
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
app = FastAPI(title="TruthGuard AI Pro")
user_credits = {"free_user": 500}
last_results = [] # Store results for download page later

UPLOAD_PAGE = """
<!DOCTYPE html>
<html>
<head>
  <title>TruthGuard AI Pro</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{ 
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial; 
      background: #0f172a; 
      color: white; 
      margin: 0; 
      padding: 20px;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
    }}
  .container {{ max-width: 700px; width: 100%; text-align: center; }}
    h1 {{ color: #38bdf8; font-size: 32px; margin-bottom: 10px; }}
    h1.shield {{ font-size: 40px; }}
  .credits {{ font-size: 18px; color: #22c55e; font-weight: bold; margin-bottom: 30px; }}
  .card {{ background: #1e293b; padding: 25px; border-radius: 16px; margin-bottom: 20px; text-align: left; }}
    textarea {{ width: 100%; height: 220px; padding: 12px; background: #0f172a; color: white; border: 1px solid #334155; border-radius: 8px; font-size: 14px; box-sizing: border-box; }}
    button {{ padding: 14px 28px; margin: 8px 5px; background: #2563eb; color: white; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; font-size: 15px; width: 100%; }}
    button:hover {{ background: #1d4ed8; }}
    input[type="file"] {{ color: #94a3b8; }}
    h3 {{ margin-top: 0; color: #cbd5e1; }}
  </style>
</head>
<body>
  <div class="container">
    <h1><span class="shield">🛡️</span> TruthGuard AI Pro</h1>
    <p class="credits">Your Credits: {credits}</p>

    <div class="card">
      <h3>Option 1: Paste Your Data</h3>
      <form action="/process" method="post" id="pasteForm">
        <textarea name="data" id="data" placeholder="Paste 1 row per line here..."></textarea>
        <button type="button" onclick="generateMessyData(5000)">⚡ Generate 5000 Messy Rows</button>
        <button type="submit">🧹 Clean Pasted Data</button>
      </form>
    </div>

    <div class="card">
      <h3>Option 2: Upload File</h3>
      <form action="/process" method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept=".csv,.txt">
        <br><br>
        <button type="submit">📁 Clean Uploaded File</button>
      </form>
    </div>
  </div>

  <script>
  function generateMessyData(n){{
    const typos = ["teh", "recieve", "adress", "iphnoe 15", "samsng s24", "nike shose"];
    const falseClaims = ["Nigeria capital is Lagos", "Water boils at 50c", "The earth is flat", "2 + 2 = 5"];
    const products = ["iPhone", "Laptop", "Shoe", "Bag", "Watch"];
    let text = "";
    for(let i=0; i<n; i++){{
      let rand = Math.random();
      if(rand < 0.5){{ text += typos[Math.floor(Math.random()*typos.length)] + " " + products[Math.floor(Math.random()*products.length)] + "\n"; }}
      else if(rand < 0.8){{ text += falseClaims[Math.floor(Math.random()*falseClaims.length)] + "\n"; }}
      else {{ text += "Brand new " + products[Math.floor(Math.random()*products.length)] + " for sale in Lagos\n"; }}
    }}
    document.getElementById("data").value = text;
    alert(n.toLocaleString() + " rows generated! Now click 'Clean Pasted Data'");
  }}
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
    gc.collect()
    return results

@app.get("/", response_class=HTMLResponse)
async def home():
    credits = user_credits.get("free_user", 500)
    if isinstance(credits, dict): credits = 500
    return HTMLResponse(UPLOAD_PAGE.format(credits=int(credits)))

@app.post("/process")
async def process_data(data: str = Form(None), file: UploadFile = File(None)):
    global last_results
    credits = user_credits.get("free_user", 500)
    if isinstance(credits, dict): credits = 500

    if file:
        content = await file.read()
        data_list = content.decode('utf-8').splitlines()
    elif data: 
        data_list = data.splitlines()
    else: 
        raise HTTPException(status_code=400, detail="No data provided")

    data_list = [d.strip() for d in data_list if d.strip()]
    credits_needed = (len(data_list) // 50 + 1) * CREDITS_PER_50_ROWS
    if credits < credits_needed: 
        return HTMLResponse(f"<h1 style='color:white; text-align:center;'>Not enough credits. Need {credits_needed}, have {credits}</h1>")

    last_results = await clean_and_verify_all(data_list)
    user_credits["free_user"] = int(credits) - credits_needed
    
    # For now just download CSV directly. Next we add the "Results Page"
    df_out = pd.DataFrame(last_results)
    csv = df_out.to_csv(index=False)
    return StreamingResponse(io.StringIO(csv), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=truthguard_cleaned.csv"})

if __name__ == "__main__": 
    uvicorn.run(app, host="0.0.0.0", port=8000)