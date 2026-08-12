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
pending_purchase = {} # store what they want to buy

NAV = """<div style="width:100%; text-align:center; padding:15px 0; background:#0f172a;"><a href="/" style="color:#22c55e; text-decoration:none; font-weight:bold; margin:0 15px;">Home</a><a href="/clean" style="color:#22c55e; text-decoration:none; font-weight:bold; margin:0 15px;">Cleaning</a><a href="/pricing" style="color:#94a3b8; text-decoration:none; font-weight:bold; margin:0 15px;">Pricing</a></div>"""

HOME_PAGE = """<!DOCTYPE html><html><head><title>TruthGuard AI Pro</title><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:Arial;background:#0f172a;color:white;margin:0}}.container{{max-width:700px;margin:0 auto;padding:20px;text-align:center}}h1{{color:#38bdf8}}.card{{background:#1e293b;padding:25px;border-radius:16px;margin-top:20px}}button{{padding:14px;background:#2563eb;color:white;border:none;border-radius:10px;font-weight:bold;width:100%}}</style></head><body>{NAV}<div class="container"><h1>🛡️ TruthGuard AI Pro</h1><p>Clean and verify 1000s of rows</p><div class="card"><a href="/clean"><button>Start Cleaning Data →</button></a></div></div></body></html>""".format(NAV=NAV)

UPLOAD_PAGE = """<!DOCTYPE html><html><head><title>Cleaning</title><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:Arial;background:#0f172a;color:white;margin:0}}.container{{max-width:700px;margin:0 auto;padding:20px;text-align:center}}h1{{color:#38bdf8}}.credits{{color:#22c55e;font-weight:bold}}.card{{background:#1e293b;padding:25px;border-radius:16px;margin-bottom:20px;text-align:left}}textarea{{width:100%;height:220px;background:#0f172a;color:white;border:1px solid #334155;border-radius:8px}}button{{padding:14px;background:#2563eb;color:white;border:none;border-radius:10px;font-weight:bold;width:100%}}</style></head><body>{NAV}<div class="container"><h1>🛡️ TruthGuard AI Pro</h1><p class="credits">Your Credits: {credits}</p><div class="card"><h3>Option 1: Paste</h3><form action="/process" method="post"><textarea name="data" id="data"></textarea><button type="button" onclick="document.getElementById('data').value='teh\n'.repeat(5000)">⚡ Generate 5000</button><button type="submit">🧹 Clean</button></form></div></div></body></html>"""

PRICING_PAGE = """<!DOCTYPE html><html><head><title>Pricing</title><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:Arial;background:#0f172a;color:white;margin:0}}.container{{max-width:700px;margin:0 auto;padding:20px;text-align:center}}h1{{color:#38bdf8}}.price-grid{{display:grid;grid-template-columns:1fr 1fr;gap:15px}}.price-card{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px}}button{{padding:12px;background:#2563eb;color:white;border:none;border-radius:8px;font-weight:bold;width:100%}}.credits-now{{color:#22c55e;font-size:20px;font-weight:bold}}</style></head><body>{NAV}<div class="container"><h1>Choose Your Plan</h1><p class="credits-now">Your Credits: {credits}</p><div class="price-grid"><div class="price-card"><h3>Free</h3><h2>$0</h2><p>500 Credits</p><button disabled>Current</button></div><div class="price-card"><h3>Starter</h3><h2>₦7,000</h2><p>500 Credits</p><form action="/checkout" method="post"><input type="hidden" name="amount" value="500"><input type="hidden" name="price" value="7000"><button>Buy Now</button></form></div><div class="price-card"><h3>Pro</h3><h2>₦50,000</h2><p>1,000 Credits</p><form action="/checkout" method="post"><input type="hidden" name="amount" value="1000"><input type="hidden" name="price" value="50000"><button>Buy Now</button></form></div><div class="price-card"><h3>Business</h3><h2>₦75,000</h2><p>10,000 Credits</p><form action="/checkout" method="post"><input type="hidden" name="amount" value="10000"><input type="hidden" name="price" value="75000"><button>Buy Now</button></form></div><div class="price-card" style="grid-column:span 2"><h3>Enterprise</h3><h2>₦150,000</h2><p>20,000 Credits</p><form action="/checkout" method="post"><input type="hidden" name="amount" value="20000"><input type="hidden" name="price" value="150000"><button>Buy Now</button></form></div></div></div></body></html>"""

CHECKOUT_PAGE = """<!DOCTYPE html><html><head><title>Checkout</title><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:Arial;background:#0f172a;color:white;margin:0}}.container{{max-width:500px;margin:0 auto;padding:20px}}h1{{color:#38bdf8;text-align:center}}.card{{background:#1e293b;padding:25px;border-radius:16px}}input{{width:100%;padding:12px;margin:8px 0;background:#0f172a;border:1px solid #334155;border-radius:8px;color:white}}button{{padding:14px;background:#22c55e;color:black;border:none;border-radius:10px;font-weight:bold;width:100%;font-size:16px}}.note{{background:#1e293b;padding:15px;border-radius:8px;margin:15px 0;color:#94a3b8}}</style></head><body>{NAV}<div class="container"><h1>Complete Payment</h1><div class="card"><h3>Order Summary</h3><p>{amount} Credits</p><h2>₦{price}</h2><div class="note"><b>Test Card:</b><br>Card: 4084 0840 8408 4081<br>Expiry: 12/30<br>CVV: 408<br>PIN: 0000</div><form action="/pay_success" method="post"><input type="text" placeholder="Card Number" value="4084 0840 8408 4081" required><input type="text" placeholder="MM/YY" value="12/30" required><input type="text" placeholder="CVV" value="408" required><button type="submit">Pay ₦{price}</button></form></div></div></body></html>"""

SYSTEM_PROMPT = """You are TruthGuard AI. Return JSON array with keys: original, cleaned, verdict, explanation"""

async def process_chunk(chunk: list) -> list:
    data_text = "\n".join([f"{i+1}. {row}" for i, row in enumerate(chunk)])
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": data_text}]
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
    return HTMLResponse(UPLOAD_PAGE.format(credits=int(credits), NAV=NAV))

@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page():
    credits = user_credits.get("free_user", 500)
    return HTMLResponse(PRICING_PAGE.format(NAV=NAV, credits=int(credits)))

# NEW: PAYMENT PAGE
@app.post("/checkout")
async def checkout(amount: int = Form(...), price: int = Form(...)):
    pending_purchase["amount"] = amount
    pending_purchase["price"] = price
    return HTMLResponse(CHECKOUT_PAGE.format(NAV=NAV, amount=amount, price=price))

# NEW: FAKE PAYMENT SUCCESS
@app.post("/pay_success")
async def pay_success():
    amount = pending_purchase.get("amount", 0)
    credits = user_credits.get("free_user", 500)
    user_credits["free_user"] = int(credits) + int(amount)
    pending_purchase.clear()
    return HTMLResponse(f"""<body style="background:#0f172a;color:white;font-family:Arial;text-align:center;padding-top:50px;"><h1 style="color:#22c55e;">Payment Successful!</h1><p>Added {amount} Credits</p><p>New Balance: {user_credits['free_user']} Credits</p><a href="/pricing"><button style="padding:12px;background:#2563eb;color:white;border:none;border-radius:8px;">Back to Pricing</button></a></body>""")

@app.post("/process")
async def process_data(data: str = Form(None), file: UploadFile = File(None)):
    global last_results
    credits = user_credits.get("free_user", 500)
    if file: data_list = (await file.read()).decode('utf-8').splitlines()
    elif data: data_list = data.splitlines()
    else: raise HTTPException(status_code=400, detail="No data")
    data_list = [d.strip() for d in data_list if d.strip()]
    credits_needed = (len(data_list) // 50 + 1) * CREDITS_PER_50_ROWS
    if credits < credits_needed: return HTMLResponse(f"<h1>Not enough credits</h1>")
    last_results = await clean_and_verify_all(data_list)
    user_credits["free_user"] = int(credits) - credits_needed
    df_out = pd.DataFrame(last_results)
    csv = df_out.to_csv(index=False)
    return StreamingResponse(io.StringIO(csv), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=truthguard_cleaned.csv"})

if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=8000)