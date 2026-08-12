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
last_results = []

NAV = """
<div style="width:100%; text-align:center; padding:15px 0; background:#0f172a;">
  <a href="/" style="color:#22c55e; text-decoration:none; font-weight:bold; margin:0 15px; font-size:16px;">Home</a>
  <a href="/clean" style="color:#22c55e; text-decoration:none; font-weight:bold; margin:0 15px; font-size:16px;">Cleaning</a>
  <a href="/pricing" style="color:#94a3b8; text-decoration:none; font-weight:bold; margin:0 15px; font-size:16px;">Pricing</a>
</div>
"""

HOME_PAGE = """
<!DOCTYPE html><html><head><title>TruthGuard AI Pro</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial; background: #0f172a; color: white; margin: 0; padding: 0; }}
.container {{ max-width: 700px; margin: 0 auto; padding: 20px; text-align: center; }}
h1 {{ color: #38bdf8; font-size: 32px; }}
.subtitle {{ color: #94a3b8; }}
.card {{ background: #1e293b; padding: 25px; border-radius: 16px; margin-top: 20px; text-align: left; }}
button {{ padding: 14px 28px; background: #2563eb; color: white; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; font-size: 15px; width: 100%; }}
</style></head>
<body>{NAV}<div class="container">
<h1><span style="font-size:40px;">🛡️</span> TruthGuard AI Pro</h1>
<p class="subtitle">Clean and verify 1000s of rows of data with AI in seconds.</p>
<div class="card"><h3>What can TruthGuard do?</h3>
<p><span style="color:#22c55e;">✅</span> Fix typos and grammar<br>
<span style="color:#22c55e;">✅</span> Fact-check claims<br>
<span style="color:#22c55e;">✅</span> Export to CSV & PDF</p>
<a href="/clean"><button>Start Cleaning Data →</button></a>
</div></div></body></html>
""".format(NAV=NAV)

UPLOAD_PAGE = """
<!DOCTYPE html><html><head><title>Cleaning - TruthGuard AI Pro</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial; background: #0f172a; color: white; margin: 0; padding: 0;}}
.container {{ max-width: 700px; width: 100%; margin: 0 auto; padding: 20px; text-align: center; }}
h1 {{ color: #38bdf8; font-size: 32px; margin-bottom: 10px; }}
.credits {{ font-size: 18px; color: #22c55e; font-weight: bold; margin-bottom: 30px; }}
.card {{ background: #1e293b; padding: 25px; border-radius: 16px; margin-bottom: 20px; text-align: left; }}
textarea {{ width: 100%; height: 220px; padding: 12px; background: #0f172a; color: white; border: 1px solid #334155; border-radius: 8px; font-size: 14px; box-sizing: border-box; }}
button {{ padding: 14px 28px; margin: 8px 5px; background: #2563eb; color: white; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; font-size: 15px; width: 100%; }}
button:hover {{ background: #1d4ed8; }}
input[type="file"] {{ color: #94a3b8; }}
h3 {{ margin-top: 0; color: #cbd5e1; }}
</style></head>
<body>{NAV}<div class="container">
<h1><span style="font-size:40px;">🛡️</span> TruthGuard AI Pro</h1>
<p class="credits">Your Credits: {credits}</p>
<div class="card"><h3>Option 1: Paste Your Data</h3>
<form action="/process" method="post"><textarea name="data" id="data" placeholder="Paste 1 row per line here..."></textarea>
<button type="button" onclick="generateMessyData(5000)">⚡ Generate 5000 Messy Rows</button>
<button type="submit">🧹 Clean Pasted Data</button></form></div>
<div class="card"><h3>Option 2: Upload File</h3>
<form action="/process" method="post" enctype="multipart/form-data">
<input type="file" name="file" accept=".csv,.txt"><br><br>
<button type="submit">📁 Clean Uploaded File</button></form></div>
</div>
<script>
function generateMessyData(n){{
let text = "";
for(let i=0; i<n; i++){{ text += "teh iphnoe 15, Nigeria capital is Lagos\n"; }}
document.getElementById("data").value = text;
alert(n.toLocaleString() + " rows generated! Now click 'Clean Pasted Data'");
}}
</script></body></html>
"""

PRICING_PAGE = """
<!DOCTYPE html><html><head><title>Pricing - TruthGuard AI Pro</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial; background: #0f172a; color: white; margin: 0; padding: 0; }}
.container {{ max-width: 700px; margin: 0 auto; padding: 20px; text-align: center; }}
h1 {{ color: #38bdf8; }}
.price-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
.price-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; }}
.price-card.pro {{ border: 2px solid #38bdf8; }}
button {{ padding: 12px 20px; background: #2563eb; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; width: 100%; font-size:15px; }}
button:hover {{ background: #1d4ed8; }}
.credits-now {{ font-size: 20px; color: #22c55e; font-weight: bold; margin-bottom: 20px; }}
</style></head>
<body>{NAV}<div class="container">
<h1>Choose Your Plan</h1>
<p class="credits-now">Your Credits: {credits}</p>
<div class="price-grid">
<div class="price-card"><h3>Free</h3><h2>$0</h2><p>500 Credits<br>50 rows/run<br>CSV Export</p><button disabled>Current</button></div>
<div class="price-card"><h3>Starter Pack</h3><h2>₦7,000</h2><p>500 Credits</p><form action="/buy_credits" method="post"><input type="hidden" name="amount" value="500"><button type="submit">Buy Now</button></form></div>
<div class="price-card"><h3>Pro Pack</h3><h2>₦50,000</h2><p>1,000 Credits</p><form action="/buy_credits" method="post"><input type="hidden" name="amount" value="1000"><button type="submit">Buy Now</button></form></div>
<div class="price-card pro"><h3>Business Pack</h3><h2>₦75,000</h2><p>10,000 Credits</p><form action="/buy_credits" method="post"><input type="hidden" name="amount" value="10000"><button type="submit">Buy Now</button></form></div>
<div class="price-card" style="grid-column: span 2;"><h3>Enterprise Pack</h3><h2>₦150,000</h2><p>20,000 Credits</p><form action="/buy_credits" method="post"><input type="hidden" name="amount" value="20000"><button type="submit">Buy Now</button></form></div>
</div></div></body></html>
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
    return HTMLResponse(HOME_PAGE)

@app.get("/clean", response_class=HTMLResponse)
async def clean_page():
    credits = user_credits.get("free_user", 500)
    return HTMLResponse(UPLOAD_PAGE.format(credits=int(credits), NAV=NAV))

@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page():
    credits = user_credits.get("free_user", 500)
    return HTMLResponse(PRICING_PAGE.format(NAV=NAV, credits=int(credits)))

# NEW ROUTE: TEST BUY CREDITS
@app.post("/buy_credits")
async def buy_credits(amount: int = Form(...)):
    credits = user_credits.get("free_user", 500)
    user_credits["free_user"] = int(credits) + amount
    return HTMLResponse(f"""
    <body style="background:#0f172a; color:white; font-family:Arial; text-align:center; padding-top:50px;">
    <h1 style="color:#22c55e;">Success! Added {amount} Credits</h1>
    <p style="font-size:20px;">New Balance: {user_credits['free_user']} Credits</p>
    <div style="margin-top:20px;"><a href="/pricing"><button style="padding:12px 24px; background:#2563eb; color:white; border:none; border-radius:8px; font-weight:bold;">Back to Pricing</button></a></div>
    </body>
    """)

@app.post("/process")
async def process_data(data: str = Form(None), file: UploadFile = File(None)):
    global last_results
    credits = user_credits.get("free_user", 500)
    if file: data_list = (await file.read()).decode('utf-8').splitlines()
    elif data: data_list = data.splitlines()
    else: raise HTTPException(status_code=400, detail="No data provided")
    data_list = [d.strip() for d in data_list if d.strip()]
    credits_needed = (len(data_list) // 50 + 1) * CREDITS_PER_50_ROWS
    if credits < credits_needed: return HTMLResponse(f"<h1 style='color:white; text-align:center;'>Not enough credits. Need {credits_needed}, have {credits}</h1>")
    last_results = await clean_and_verify_all(data_list)
    user_credits["free_user"] = int(credits) - credits_needed
    df_out = pd.DataFrame(last_results)
    csv = df_out.to_csv(index=False)
    return StreamingResponse(io.StringIO(csv), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=truthguard_cleaned.csv"})

if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=8000)