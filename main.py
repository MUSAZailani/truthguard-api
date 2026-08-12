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
pending_purchase = {} # store what they want to buy

NAV = """<div style="width:100%; text-align:center; padding:15px 0; background:#0f172a;"><a href="/" style="color:#22c55e; text-decoration:none; font-weight:bold; margin:0 15px; font-size:16px;">Home</a><a href="/clean" style="color:#22c55e; text-decoration:none; font-weight:bold; margin:0 15px; font-size:16px;">Cleaning</a><a href="/pricing" style="color:#94a3b8; text-decoration:none; font-weight:bold; margin:0 15px; font-size:16px;">Pricing</a></div>"""

HOME_PAGE = """<!DOCTYPE html><html><head><title>TruthGuard AI Pro</title><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial;background:#0f172a;color:white;margin:0;padding:0}}.container{{max-width:700px;margin:0 auto;padding:20px;text-align:center}}h1{{color:#38bdf8;font-size:32px}}.subtitle{{color:#94a3b8}}.card{{background:#1e293b;padding:25px;border-radius:16px;margin-top:20px;text-align:left}}button{{padding:14px 28px;background:#2563eb;color:white;border:none;border-radius:10px;cursor:pointer;font-weight:bold;font-size:15px;width:100%}}</style></head><body>{NAV}<div class="container"><h1><span style="font-size:40px;">🛡️</span> TruthGuard AI Pro</h1><p class="subtitle">Clean and verify 1000s of rows of data with AI in seconds.</p><div class="card"><h3>What can TruthGuard do?</h3><p><span style="color:#22c55e;">✅</span> Fix typos and grammar<br><span style="color:#22c55e;">✅</span> Fact-check claims<br><span style="color:#22c55e;">✅</span> Export to CSV & PDF</p><a href="/clean"><button>Start Cleaning Data →</button></a></div></div></body></html>""".format(NAV=NAV)

UPLOAD_PAGE = """<!DOCTYPE html><html><head><title>Cleaning - TruthGuard AI Pro</title><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial;background:#0f172a;color:white;margin:0;padding:0}}.container{{max-width:700px;width:100%;margin:0 auto;padding:20px;text-align:center}}h1{{color:#38bdf8;font-size:32px;margin-bottom:10px}}.credits{{font-size:18px;color:#22c55e;font-weight:bold;margin-bottom:30px}}.card{{background:#1e293b;padding:25px;border-radius:16px;margin-bottom:20px;text-align:left}}textarea{{width:100%;height:220px;padding:12px;background:#0f172a;color:white;border:1px solid #334155;border-radius:8px;font-size:14px;box-sizing:border-box}}button{{padding:14px 28px;margin:8px 5px;background:#2563eb;color:white;border:none;border-radius:10px;cursor:pointer;font-weight:bold;font-size:15px;width:100%}}button:hover{{background:#1d4ed8}}input[type="file"]{{color:#94a3b8}}h3{{margin-top:0;color:#cbd5e1}}</style></head><body>{NAV}<div class="container"><h1><span style="font-size:40px;">🛡️</span> TruthGuard AI Pro</h1><p class="credits">Your Credits: {credits}</p><div class="card"><h3>Option 1: Paste Your Data</h3><form action="/process" method="post"><textarea name="data" id="data" placeholder="Paste 1 row per line here..."></textarea><button type="button" onclick="document.getElementById('data').value='teh iphnoe 15\n'.repeat(5000)">⚡ Generate 5000 Messy Rows</button><button type="submit">🧹 Clean Pasted Data</button></form></div><div class="card"><h3>Option 2: Upload File</h3><form action="/process" method="post" enctype="multipart/form-data"><input type="file" name="file" accept=".csv,.txt"><br><br><button type="submit">📁 Clean Uploaded File</button></form></div></div></body></html>"""

PRICING_PAGE = """<!DOCTYPE html><html><head><title>Pricing - TruthGuard AI Pro</title><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial;background:#0f172a;color:white;margin:0;padding:0}}.container{{max-width:700px;margin:0 auto;padding:20px;text-align:center}}h1{{color:#38bdf8}}.price-grid{{display:grid;grid-template-columns:1fr 1fr;gap:15px}}.price-card{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px}}.price-card.pro{{border:2px solid #38bdf8}}button{{padding:12px 20px;background:#2563eb;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;width:100%;font-size:15px}}button:hover{{background:#1d4ed8}}.credits-now{{font-size:20px;color:#22c55e;font-weight:bold;margin-bottom:20px}}</style></head><body>{NAV}<div class="container"><h1>Choose Your Plan</h1><p class="credits-now">Your Credits: {credits}</p><div class="price-grid"><div class="price-card"><h3>Free</h3><h2>$0</h2><p>500 Credits<br>50 rows/run<br>CSV Export</p><button disabled>Current</button></div><div class="price-card"><h3>Starter Pack</h3><h2>₦7,000</h2><p>500 Credits</p><form action="/checkout" method="post"><input type="hidden" name="amount" value="500"><input type="hidden" name="price" value="7000"><button type="submit">Buy Now</button></form></div><div class="price-card"><h3>Pro Pack</h3><h2>₦50,000</h2><p>1,000 Credits</p><form action="/checkout" method="post"><input type="hidden" name="amount" value="1000"><input type="hidden" name="price" value="50000"><button type="submit">Buy Now</button></form></div><div class="price-card pro"><h3>Business Pack</h3><h2>₦75,000</h2><p>10,000 Credits</p><form action="/checkout" method="post"><input type="hidden" name="amount" value="10000"><input type="hidden" name="price" value="75000"><button type="submit">Buy Now</button></form></div><div class="price-card" style="grid-column:span 2"><h3>Enterprise Pack</h3><h2>₦150,000</h2><p>20,000 Credits</p><form action="/checkout" method="post"><input type="hidden" name="amount" value="20000"><input type="hidden" name="price" value="150000"><button type="submit">Buy Now</button></form></div></div></div></body></html>"""

CHECKOUT_PAGE = """<!DOCTYPE html><html><head><title>Checkout - TruthGuard AI Pro</title><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial;background:#0f172a;color:white;margin:0;padding:0}}.container{{max-width:500px;margin:0 auto;padding:20px}}h1{{color:#38bdf8;text-align:center}}.card{{background:#1e293b;padding:25px;border-radius:16px}}.method{{border:1px solid #334155;border-radius:10px;padding:15px;margin:10px 0;cursor:pointer;font-weight:bold}}.method:hover{{border-color:#38bdf8}}.method.active{{border-color:#22c55e;background:#132e1f}}input{{width:100%;padding:12px;margin:8px 0;background:#0f172a;border:1px solid #334155;border-radius:8px;color:white;box-sizing:border-box}}button{{padding:14px;background:#22c55e;color:black;border:none;border-radius:10px;font-weight:bold;width:100%;font-size:16px}}.note{{background:#0f172a;padding:15px;border-radius:8px;margin:15px 0;color:#94a3b8;font-size:14px;border:1px dashed #334155}}.hidden{{display:none}}</style><script>function selectMethod(m){{document.querySelectorAll('.method').forEach(e=>e.classList.remove('active'));document.getElementById(m).classList.add('active');document.querySelectorAll('.pay-form').forEach(e=>e.classList.add('hidden'));document.getElementById('form-'+m).classList.remove('hidden');}}</script></head><body>{NAV}<div class="container"><h1>Complete Payment</h1><div class="card"><h3>Order Summary</h3><p>{amount} Credits</p><h2>₦{price}</h2><h4>Choose Payment Method</h4><div class="method active" id="card" onclick="selectMethod('card')">💳 Card</div><div class="method" id="bank" onclick="selectMethod('bank')">🏦 Bank Transfer</div><div class="method" id="ussd" onclick="selectMethod('ussd')">📱 USSD</div><div class="method" id="wallet" onclick="selectMethod('wallet')">👛 Wallet</div><form id="form-card" class="pay-form" action="/pay_success" method="post"><div class="note"><b>Test Card:</b><br>Card: 4084 0840 8408 4081<br>Expiry: 12/30 | CVV: 408 | PIN: 0000</div><input type="text" placeholder="Card Number" value="4084 0840 8408 4081" required><input type="text" placeholder="MM/YY" value="12/30" required><input type="text" placeholder="CVV" value="408" required><button type="submit">Pay ₦{price} with Card</button></form><form id="form-bank" class="pay-form hidden" action="/pay_success" method="post"><div class="note"><b>Test Bank Transfer:</b><br>Account: 1234567890<br>Bank: Test Bank</div><p>Click to simulate bank transfer approval</p><button type="submit">Pay ₦{price} with Bank Transfer</button></form><form id="form-ussd" class="pay-form hidden" action="/pay_success" method="post"><div class="note"><b>Test USSD:</b><br>Dial *737*1*{price}#</div><p>Click to simulate USSD approval</p><button type="submit">Pay ₦{price} with USSD</button></form><form id="form-wallet" class="pay-form hidden" action="/pay_success" method="post"><div class="note"><b>Test Wallet:</b><br>Balance: ₦500,000</div><p>Click to pay from wallet balance</p><button type="submit">Pay ₦{price} with Wallet</button></form></div></div></body></html>"""

SYSTEM_PROMPT = """You are TruthGuard AI. Your job is to clean text and fact-check it. For each input line, return a JSON array of objects. Each object has 4 keys: "original", "cleaned", "verdict", "explanation" Verdict must be one of: True, False, Partially True Return ONLY the JSON array. No extra text, no markdown."""

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
async def home(): return HTMLResponse(HOME_PAGE)

@app.get("/clean", response_class=HTMLResponse)
async def clean_page():
    credits = user_credits.get("free_user", 500)
    return HTMLResponse(UPLOAD_PAGE.format(credits=int(credits), NAV=NAV))

@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page():
    credits = user_credits.get("free_user", 500)
    return HTMLResponse(PRICING_PAGE.format(NAV=NAV, credits=int(credits)))

@app.post("/checkout")
async def checkout(amount: int = Form(...), price: int = Form(...)):
    pending_purchase["amount"] = amount
    pending_purchase["price"] = price
    return HTMLResponse(CHECKOUT_PAGE.format(NAV=NAV, amount=amount, price=price))

@app.post("/pay_success")
async def pay_success():
    amount = pending_purchase.get("amount", 0)
    credits = user_credits.get("free_user", 500)
    user_credits["free_user"] = int(credits) + int(amount)
    pending_purchase.clear()
    return HTMLResponse(f"""<body style="background:#0f172a;color:white;font-family:Arial;text-align:center;padding-top:50px;"><h1 style="color:#22c55e;">Payment Successful!</h1><p>Added {amount} Credits</p><p style="font-size:20px;">New Balance: {user_credits['free_user']} Credits</p><a href="/pricing"><button style="padding:12px 24px;background:#2563eb;color:white;border:none;border-radius:8px;font-weight:bold;">Back to Pricing</button></a></body>""")

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