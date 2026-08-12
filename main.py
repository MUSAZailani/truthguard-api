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
MODEL = "llama-3.1-8b-instant"
CREDITS_PER_50_ROWS = 1
CHUNK_SIZE = 50
RETRY_DELAY = 2

client = Groq(api_key=GROQ_API_KEY)
app = FastAPI(title="TruthGuard AI v1.1")
user_credits = {"free_user": 500}

# NOTE: ALL {{ and }} to escape the.format() bug
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
  <title>TruthGuard AI Pro</title>
  <style>
    body {{ font-family: Arial; max-width: 900px; margin: 40px auto; padding: 20px; }}
    textarea {{ width: 100%; height: 300px; padding: 10px; }}
    button {{ padding: 12px 24px; margin: 5px; background: #2563eb; color: white; border: none; border-radius: 8px; cursor: pointer; }}
  .credits {{ font-size: 18px; font-weight: bold; color: green; }}
  </style>
</head>
<body>
  <h1>🛡️ TruthGuard AI Pro</h1>
  <p class="credits">Your Credits: {credits}</p>

  <form action="/process" method="post" enctype="multipart/form-data">
    <h3>Option 1: Paste Your Data</h3>
    <textarea name="data" id="data"></textarea><br>
    <button type="button" onclick="generateMessyData(5000)">Generate 5000 Messy Rows</button>
    <h3>Option 2: Upload File</h3>
    <input type="file" name="file"><br><br>
    <button type="submit">Clean My Data</button>
  </form>
  <script>
  function generateMessyData(n){{
    let text = "";
    for(let i=0; i<n; i++){{ text += "teh iphnoe 15 $" + Math.floor(Math.random()*1000) + "\n"; }}
    document.getElementById("data").value = text;
    alert(n + " rows generated!");
  }}
  </script>
</body>
</html>
"""

SYSTEM_PROMPT = """You are TruthGuard AI. Return JSON array with keys: original, cleaned, verdict, explanation"""

async def process_chunk(chunk: list) -> list:
    data_text = "\n".join([f"{i+1}. {row}" for i, row in enumerate(chunk)])
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": data_text}]
    response = client.chat.completions.create(model=MODEL, messages=messages, temperature=0, response_format={"type": "json_object"})
    content = response.choices[0].message.content.strip().replace("```json", "").replace("```", "")
    return json.loads(content)

async def clean_and_verify_all(data: list) -> list:
    results = []
    for i in range(0, len(data), CHUNK_SIZE):
        results.extend(process_chunk(data[i:i + CHUNK_SIZE]))
        await asyncio.sleep(RETRY_DELAY)
    return results

@app.get("/", response_class=HTMLResponse)
async def home():
    credits = user_credits.get("free_user", 500)
    return HTMLResponse(HTML_PAGE.format(credits=int(credits))) # ONLY THING CHANGED

@app.post("/process")
async def process_data(data: str = Form(None), file: UploadFile = File(None)):
    #... your original process code here, unchanged...
    content = await file.read() if file else data
    data_list = content.decode('utf-8').splitlines() if file else data.splitlines()
    data_list = [d.strip() for d in data_list if d.strip()]
    results = await clean_and_verify_all(data_list)
    df_out = pd.DataFrame(results)
    csv = df_out.to_csv(index=False)
    return StreamingResponse(io.StringIO(csv), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=truthguard_cleaned.csv"})

if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=8000)