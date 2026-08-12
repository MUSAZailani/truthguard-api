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

NAV = """
<div style="text-align:center; padding:15px 0; border-bottom:1px solid #e2e8f0; margin-bottom:20px;">
  <a href="/" style="color:#22c55e; text-decoration:none; font-weight:bold; margin:0 15px; font-size:16px;">Home</a>
  <a href="/clean" style="color:#22c55e; text-decoration:none; font-weight:bold; margin:0 15px; font-size:16px;">Cleaning</a>
  <a href="/pricing" style="color:#64748b; text-decoration:none; font-weight:bold; margin:0 15px; font-size:16px;">Pricing</a>
</div>
"""

BASE_CSS = """
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial; background: white; color: #0f172a; margin:0; padding:0; }}
.container {{ max-width: 700px; margin: 0 auto; padding: 20px; text-align: center; }}
h1 {{ color: #0f172a; font-size: 28px; margin-bottom: 10px; }}
.subtitle {{ color: #64748b; font-size: 16px; }}
.credits {{ font-size: 18px; color: #16a34a; font-weight: bold; margin-bottom: 20px; }}
.card {{ background: #f8fafc; padding: 20px; border-radius: 12px; margin-bottom: 20px; text-align: left; border:1px solid #e2e8f0; }}
textarea {{ width: 100%; height: 200px; padding: 12px; background: white; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; box-sizing: border-box; }}
button {{ padding: 12px 20px; margin: 8px 0; background: #2563eb; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 15px; width: 100%; }}
button:hover {{ background: #1d4ed8; }}
.price-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
.price-card {{ border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; }}
.price-card.pro {{ border: 2px solid #2563eb; }}
.check {{ color: #16a34a; }}
"""

HOME_PAGE = f"""
<!DOCTYPE html><html><head><title>TruthGuard AI Pro</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>{BASE_CSS}</style></head>
<body>{NAV}<div class="container">
  <div style="font-size:40px;">🛡️</div>
  <h1>TruthGuard AI Pro</h1>
  <p class="subtitle">Clean and verify 1000s of rows of data with AI in seconds.</p>
  <h3>What can TruthGuard do?</h3>
  <p style="text-align:left; display:inline-block;"><span class="check">✅</span> Fix typos and grammar<br>
  <span class="check">✅</span> Fact-check claims<br>
  <span class="check">✅</span> Export to CSV & PDF</p>
  <a href="/clean"><button>Start Cleaning Data →</button></a>
</div></body></html>
"""

CLEAN_PAGE = """
<!DOCTYPE html><html><head><title>Cleaning - TruthGuard AI Pro</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>{BASE_CSS}</style></head>
<body>{NAV}<div class="container">
  <div style="font-size:40px;">🛡️</div>
  <h1>TruthGuard AI Pro</h1>
  <p class="credits">Your Credits: {credits}</p>

  <div class="card">
    <h3>Option 1: Paste Your Data</h3>
    <form action="/process" method="post">
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
  let text = "";
  for(let i=0; i<n; i++){{ text += "teh iphnoe 15, Nigeria capital is Lagos\n"; }}
  document.getElementById("data").value = text;
  alert(n.toLocaleString() + " rows generated!");
}}
</script>
</body></html>
"""

# 4 PLANS LIKE YOU ASKED
PRICING_PAGE = f"""
<!DOCTYPE html><html><head><title>Pricing - TruthGuard AI Pro</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>{BASE_CSS}</style></head>
<body>{NAV}<div class="container">
  <h1>Choose Your Plan</h1>
  <div class="price-grid">
    <div class="price-card">
      <h3>Free</h3><h2>$0</h2>
      <p>500 Credits<br>50 rows/run<br>CSV Export</p><button disabled>Current</button>
    </div>
    <div class="price-card">
      <h3>Starter</h3><h2>$4<span style="font-size:14px;">/mo</span></h2>
      <p>2,500 Credits<br>200 rows/run<br>CSV + PDF</p><button>Upgrade</button>
    </div>
    <div class="price-card pro">
      <h3>Pro</h3><h2>$9<span style="font-size:14px;">/mo</span></h2>
      <p>10,000 Credits<br>Unlimited rows<br>Priority Speed</p><button>Upgrade</button>
    </div>
    <div class="price-card">
      <h3>Business</h3><h2>$29<span style="font-size:14px;">/mo</span></h2>
      <p>50,000 Credits<br>API Access<br>Team Seats</p><button>Upgrade</button>
    </div>
  </div>
</div></body></html>
"""

async def process_chunk(chunk: list) -> list:
    data_text = "\n".join([f"{i+1}. {row}" for i, row in enumerate(chunk)])
    messages = [{"role": "system", "content": "Return JSON array with keys: original, cleaned, verdict, explanation"}, {"role": "user", "content": data_text}]
    response = client.chat.completions.create(model=MODEL, messages=messages, temperature=0, response_format={"type": "json_object"})
    return json.loads(response.choices[0].message.content.strip().replace("```json", "").replace("```", ""))

async def clean_and_verify_all(data: list) -> list:
    results = []
    for i in range(0, len(data), CHUNK_SIZE):
        results.extend(await process_chunk(data[i:i + CHUNK_SIZE]))
        await asyncio.sleep(RETRY_DELAY)
    return results

@app.get("/", response_class=HTMLResponse)
async def home(): return HTMLResponse(HOME_PAGE)

@app.get("/clean", response_class=HTMLResponse)
async def clean_page():
    credits = user_credits.get("free_user", 500)
    return HTMLResponse(CLEAN_PAGE.format(credits=int(credits), NAV=NAV, BASE_CSS=BASE_CSS))

@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(): return HTMLResponse(PRICING_PAGE)

@app.post("/process")
async def process_data(data: str = Form(None), file: UploadFile = File(None)):
    if file: data_list = (await file.read()).decode('utf-8').splitlines()
    elif data: data_list = data.splitlines()
    else: raise HTTPException(status_code=400, detail="No data")
    data_list = [d.strip() for d in data_list if d.strip()]
    results = await clean_and_verify_all(data_list)
    df_out = pd.DataFrame(results)
    csv = df_out.to_csv(index=False)
    return StreamingResponse(io.StringIO(csv), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=truthguard_cleaned.csv"})

if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=8000)