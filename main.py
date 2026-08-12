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
MODEL = "llama-3.1-8b-instant"
CREDITS_PER_50_ROWS = 1
CHUNK_SIZE = 50
RETRY_DELAY = 2

client = Groq(api_key=GROQ_API_KEY)
app = FastAPI(title="TruthGuard AI Pro")
user_credits = {"free_user": 500}
last_results = []

NAV = """
<div style="text-align:center; margin-bottom:30px;">
  <a href="/" style="color:#22c55e; text-decoration:none; font-weight:bold; margin:0 15px; font-size:18px;">Home</a>
  <a href="/clean" style="color:#22c55e; text-decoration:none; font-weight:bold; margin:0 15px; font-size:18px;">Cleaning</a>
  <a href="/pricing" style="color:#64748b; text-decoration:none; font-weight:bold; margin:0 15px; font-size:18px;">Pricing</a>
</div>
"""

BASE_CSS = """
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial;
  background: #0f172a;
  color: white;
  margin: 0;
  padding: 20px;
  display: flex;
  justify-content: center;
}}
.container {{ max-width: 700px; width: 100%; text-align: center; }}
h1 {{ color: #38bdf8; font-size: 32px; margin-bottom: 10px; }}
.credits {{ font-size: 18px; color: #22c55e; font-weight: bold; margin-bottom: 30px; }}
.card {{ background: #1e293b; padding: 25px; border-radius: 16px; margin-bottom: 20px; text-align: left; }}
textarea {{ width: 100%; height: 220px; padding: 12px; background: #0f172a; color: white; border: 1px solid #334155; border-radius: 8px; font-size: 14px; box-sizing: border-box; }}
button {{ padding: 14px 28px; margin: 8px 5px; background: #2563eb; color: white; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; font-size: 15px; width: 100%; }}
button:hover {{ background: #1d4ed8; }}
"""

# 1. HOME PAGE
HOME_PAGE = f"""
<!DOCTYPE html><html><head><title>TruthGuard AI Pro</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>{BASE_CSS}</style></head>
<body><div class="container">
  {NAV}
  <h1><span style="font-size:40px;">🛡️</span> TruthGuard AI Pro</h1>
  <p style="color:#94a3b8; font-size:18px;">Clean and verify 1000s of rows of data with AI in seconds.</p>
  <div class="card" style="text-align:center;">
    <h3>What can TruthGuard do?</h3>
    <p>✅ Fix typos and grammar<br>✅ Fact-check claims<br>✅ Export to CSV & PDF</p>
    <a href="/clean"><button>Start Cleaning Data →</button></a>
  </div>
</div></body></html>
"""

# 2. CLEANING PAGE - YOUR EXACT UI
CLEAN_PAGE = """
<!DOCTYPE html><html><head><title>Cleaning - TruthGuard AI Pro</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>{BASE_CSS}</style></head>
<body><div class="container">
  {NAV}
  <h1><span style="font-size:40px;">🛡️</span> TruthGuard AI Pro</h1>
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
      <input type="file" name="file" accept=".csv,.txt" style="color:#94a3b8;">
      <br><br>
      <button type="submit">📁 Clean Uploaded File</button>
    </form>
  </div>
</div>
<script>
function generateMessyData(n){{
  const typos = ["teh", "recieve", "adress", "iphnoe 15", "samsng s24"];
  const falseClaims = ["Nigeria capital is Lagos", "Water boils at 50c", "The earth is flat"];
  let text = "";
  for(let i=0; i<n; i++){{ text += typos[Math.floor(Math.random()*typos.length)] + "\n"; }}
  document.getElementById("data").value = text;
  alert(n.toLocaleString() + " rows generated! Now click 'Clean Pasted Data'");
}}
</script>
</body></html>
"""

# 3. PRICING PAGE
PRICING_PAGE = f"""
<!DOCTYPE html><html><head><title>Pricing - TruthGuard AI Pro</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>{BASE_CSS}.price-card {{ border: 2px solid #334155; }}</style></head>
<body><div class="container">
  {NAV}
  <h1>Pricing Plans</h1>
  <div class="card price-card">
    <h2>Free Plan</h2>
    <h1>$0</h1>
    <p>500 Credits<br>50 rows per run<br>CSV Export</p>
    <button disabled>Current Plan</button>
  </div>
  <div class="card price-card" style="border-color:#38bdf8;">
    <h2>Pro Plan</h2>
    <h1>$9<span style="font-size:16px;">/month</span></h1>
    <p>10,000 Credits<br>Unlimited rows<br>PDF + CSV Export<br>Priority Speed</p>
    <button>Upgrade Soon</button>
  </div>
</div></body></html>
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
        results.extend(await process_chunk(data[i:i + CHUNK_SIZE]))
        await asyncio.sleep(RETRY_DELAY)
    gc.collect()
    return results

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse(HOME_PAGE)

@app.get("/clean", response_class=HTMLResponse)
async def clean_page():
    credits = user_credits.get("free_user", 500)
    return HTMLResponse(CLEAN_PAGE.format(credits=int(credits), NAV=NAV, BASE_CSS=BASE_CSS))

@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page():
    return HTMLResponse(PRICING_PAGE)

@app.post("/process")
async def process_data(data: str = Form(None), file: UploadFile = File(None)):
    global last_results
    credits = user_credits.get("free_user", 500)
    if file: data_list = (await file.read()).decode('utf-8').splitlines()
    elif data: data_list = data.splitlines()
    else: raise HTTPException(status_code=400, detail="No data provided")
    data_list = [d.strip() for d in data_list if d.strip()]

    credits_needed = (len(data_list) // 50 + 1) * CREDITS_PER_50_ROWS
    if credits < credits_needed: return HTMLResponse(f"<h1>Not enough credits. Need {credits_needed}</h1>")

    last_results = await clean_and_verify_all(data_list)
    user_credits["free_user"] = int(credits) - credits_needed
    df_out = pd.DataFrame(last_results)
    csv = df_out.to_csv(index=False)
    return StreamingResponse(io.StringIO(csv), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=truthguard_cleaned.csv"})

if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=8000)