from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
import pandas as pd
import io
import uuid
import base64
import re
import json
import os
import requests

app = FastAPI(title="TruthGuard AI")

DB_FILE = "users.json"
NEW_USER_CREDITS = 500
PAYSTACK_LIVE_KEY = os.getenv("PAYSTACK_LIVE_KEY")

PLANS = {
    "500": {"price": 7000, "credits": 500, "name": "Starter"},
    "1000": {"price": 50000, "credits": 1000, "name": "Pro"},
    "10000": {"price": 75000, "credits": 10000, "name": "Business"},
    "20000": {"price": 150000, "credits": 20000, "name": "Enterprise"}
}

def load_users():
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f: return json.load(f)
    except: pass
    return {}

def save_users(users):
    try:
        with open(DB_FILE, "w") as f: json.dump(users, f)
    except: pass # Railway may block writes, but we try

USERS = load_users()

def get_session(request: Request):
    session_id = request.cookies.get("tg_session")
    if not session_id:
        session_id = str(uuid.uuid4())
    if session_id not in USERS:
        USERS[session_id] = NEW_USER_CREDITS
        save_users(USERS)
    return session_id

def get_credits(session_id): 
    global USERS
    USERS = load_users() # RELOAD EVERY TIME for Railway
    return USERS.get(session_id, NEW_USER_CREDITS)

def use_credits(session_id, amount):
    global USERS
    USERS = load_users() # RELOAD FIRST
    if session_id in USERS and USERS[session_id] >= amount:
        USERS[session_id] -= amount
        save_users(USERS)
        return True
    return False

SPELL_DICT = {"banananas": "bananas", "recieve": "receive", "teh": "the", "adress": "address", "seperate": "separate"}

def clean_text(text):
    if pd.isna(text): return ""
    text = str(text).strip()
    text = re.sub(r'\s+', ' ', text) # only fix spacing
    words = text.split()
    words = [words[i] for i in range(len(words)) if i == 0 or words[i].lower()!= words[i-1].lower()] # remove repeat words only
    words = [SPELL_DICT.get(w.lower(), w) for w in words] # fix small typos
    return " ".join(words)

def smart_clean(df: pd.DataFrame):
    df = df.astype(str)
    for col in df.columns: df[col] = df[col].apply(clean_text)
    df = df.drop_duplicates() # keep this
    # REMOVED: df.dropna(how='all') <- this was deleting too much
    df = df.replace('nan', '').replace('None', '')
    return df

def NAVBAR(credits):
    return f"""<div style="background:#0d0d0d;padding:15px 20px;border-bottom:2px solid #00ff88;position:sticky;top:0;z-index:100">
<div style="max-width:900px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap">
<div style="display:flex;align-items:center;gap:10px"><span style="font-size:2em">🛡️</span><b style="font-size:1.3em;color:#00ff88">TruthGuard AI</b></div>
<div style="display:flex;gap:25px;align-items:center;flex-wrap:wrap">
<a href="/" style="color:#fff;text-decoration:none;font-weight:bold">Home</a>
<a href="/clean" style="color:#fff;text-decoration:none;font-weight:bold">Cleaning</a>
<a href="/pricing" style="color:#fff;text-decoration:none;font-weight:bold">Pricing</a>
<div style="background:#1a1a1a;padding:8px 18px;border-radius:25px;border:1px solid #333">Credits: {credits}</div>
</div></div></div>"""

CSS = """<style>
body{background:#0a0a0a;color:#e0e0e0;font-family:Arial, sans-serif;margin:0;padding:0}
.container{max-width:1000px;margin:0 auto;padding:30px 20px}
.btn{background:#00ff88;color:#000;padding:16px 25px;border-radius:10px;text-decoration:none;font-weight:bold;display:inline-block;font-size:1em;border:none;cursor:pointer;width:100%;margin:8px 0}
.btn:hover{background:#00dd77}
.btn-secondary{background:#1a1a1a;color:#fff;border:1px solid #333}
input,textarea{width:100%;padding:14px;margin:12px 0;border-radius:10px;border:1px solid #333;background:#111;color:#fff;box-sizing:border-box;font-size:1em}
.error{color:#ff4444;font-weight:bold;text-align:center;padding:12px;background:#1a0000;border:1px solid #ff4444;border-radius:8px;margin:15px 0}
.success{color:#00ff88;font-weight:bold;text-align:center;padding:12px;background:#001a00;border:1px solid #00ff88;border-radius:8px;margin:15px 0}
.download{background:#00ff88;color:#000;padding:14px;text-align:center;border-radius:10px;text-decoration:none;display:block;font-weight:bold;margin:15px 0}
.card{background:#111;padding:30px;border-radius:15px;border:2px solid #333;text-align:center}
.grid{display:grid;grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));gap:20px;margin-top:20px}
.price{font-size:2.5em;font-weight:bold;color:#00ff88;margin:10px 0}
</style>"""

def HOME_PAGE(credits): return f"<!DOCTYPE html><html><head><title>TruthGuard AI</title><meta name=viewport content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{NAVBAR(credits)}<div class=container style=text-align:center><div style=font-size:5em;margin:20px 0>🛡️</div><h1 style=color:#00ff88>TruthGuard AI</h1><p style=color:#aaa;font-size:1.2em>AI Powered CSV & Text Cleaning</p><p style=color:#00ff88>Handles 5000+ rows instantly • 1 Credit = 1 Row</p><p style=color:#00ff88;font-size:1.1em>New Users Get {NEW_USER_CREDITS} Free Credits</p><div style=margin-top:40px><a href=/clean class=btn>CLEAN DATA</a></div></div></body></html>"
def CLEAN_PAGE(credits, message="", msg_class="", download_link="", disabled=""): return f"<!DOCTYPE html><html><head><title>Cleaning - TruthGuard AI</title><meta name=viewport content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{NAVBAR(credits)}<div class=container><h1 style=text-align:center;color:#00ff88>Cleaning</h1><p class={msg_class}>{message}</p>{download_link}<form method=post enctype=multipart/form-data><label><b>Upload CSV/TXT File:</b></label><input type=file name=file accept=.csv,.txt {disabled}><label><b>Or Paste Data Here:</b></label><textarea name=text_data rows=12 placeholder='Paste up to 5000 rows...' {disabled}></textarea><button type=submit class=btn {disabled}>CLEAN DATA</button></form></div></body></html>"
def PRICING_PAGE(credits):
    cards = ""
    for key, plan in PLANS.items():
        cards += f"""<div class=card><h2>{plan['name']}</h2><div class=price>₦{plan['price']:,}</div><p>{plan['credits']:,} Credits</p><a href=/checkout/{key} class=btn>Buy Now</a></div>"""
    return f"<!DOCTYPE html><html><head><title>Pricing - TruthGuard AI</title><meta name=viewport content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{NAVBAR(credits)}<div class=container><h1 style=text-align:center;color:#00ff88>Choose Your Plan</h1><p style=text-align:center;color:#aaa>Pay once. Use forever. 1 Credit = 1 Row Cleaned</p><div class=grid>{cards}</div></div></body></html>"
def CHECKOUT_PAGE(credits, plan_key):
    plan = PLANS[plan_key]
    return f"<!DOCTYPE html><html><head><title>Checkout - TruthGuard AI</title><meta name=viewport content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{NAVBAR(credits)}<div class=container style=max-width:500px><h1 style=text-align:center;color:#00ff88>Complete Payment</h1><div class=card><h2>{plan['name']} Plan</h2><div class=price>₦{plan['price']:,}</div><p>{plan['credits']:,} Credits</p><hr style=border-color:#333;margin:20px 0><h3 style=text-align:center>Choose Payment Method</h3><form method=post action=/pay><input type=hidden name=plan value={plan_key}><button class=btn name=method value=card>Pay with Card</button><button class=btn btn-secondary name=method value=bank>Pay with Bank</button><button class=btn btn-secondary name=method value=ussd>Pay with USSD</button><button class=btn btn-secondary name=method value=qr>Pay with QR</button></form><br><a href=/pricing style=color:#00ff88>← Back to Plans</a></div></div></body></html>"

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    session_id = get_session(request)
    response = HTMLResponse(HOME_PAGE(get_credits(session_id)))
    response.set_cookie("tg_session", session_id)
    return response

@app.get("/clean", response_class=HTMLResponse)
async def clean_page(request: Request):
    session_id = get_session(request)
    credits = get_credits(session_id)
    disabled = "disabled" if credits <= 0 else ""
    message = "kindly buy credits to continue" if credits <= 0 else ""
    response = HTMLResponse(CLEAN_PAGE(credits, message, "error" if credits <= 0 else "", disabled))
    response.set_cookie("tg_session", session_id)
    return response

@app.post("/clean", response_class=HTMLResponse)
async def clean_data(request: Request, file: UploadFile = File(None), text_data: str = Form(None)):
    session_id = get_session(request)
    credits = get_credits(session_id)
    if credits <= 0: return HTMLResponse(CLEAN_PAGE(0, "kindly buy credits to continue", "error", "", "disabled"))
    if not file and not text_data: return HTMLResponse(CLEAN_PAGE(credits, "Please upload a file or paste data first", "error", "", ""))
    try:
        if file and file.filename: df = pd.read_csv(file.file, header=None, names=["data"], on_bad_lines='skip', low_memory=False)
        else: df = pd.read_csv(io.StringIO(text_data), header=None, names=["data"], on_bad_lines='skip', low_memory=False)
        rows = len(df)
        if credits < rows: return HTMLResponse(CLEAN_PAGE(credits, f"Not enough credits. This will cost {rows} credits. You have {credits}.", "error", "", ""))
        df_cleaned = smart_clean(df)
        use_credits(session_id, rows) # DEDUCT BEFORE DOWNLOAD
        new_credits = get_credits(session_id) # RELOAD TO SHOW CORRECT
        output = io.StringIO()
        df_cleaned.to_csv(output, index=False, header=False)
        b64_data = base64.b64encode(output.getvalue().encode()).decode()
        download_link = f'<a href="/download/{b64_data}" class="download">⬇️ Download Cleaned CSV - {len(df_cleaned)} rows</a>'
        message = f"✅ Cleaned {rows} rows! {rows} Credits Used. You have {new_credits} left."
        return HTMLResponse(CLEAN_PAGE(new_credits, message, "success", download_link, ""))
    except Exception as e: return HTMLResponse(CLEAN_PAGE(credits, f"Error: {str(e)}", "error", "", ""))

@app.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    session_id = get_session(request)
    response = HTMLResponse(PRICING_PAGE(get_credits(session_id)))
    response.set_cookie("tg_session", session_id)
    return response

@app.get("/checkout/{plan_key}", response_class=HTMLResponse)
async def checkout(request: Request, plan_key: str):
    session_id = get_session(request)
    if plan_key not in PLANS: return RedirectResponse("/pricing")
    response = HTMLResponse(CHECKOUT_PAGE(get_credits(session_id), plan_key))
    response.set_cookie("tg_session", session_id)
    return response

@app.post("/pay")
async def pay(request: Request, plan: str = Form(...), method: str = Form(...)):
    session_id = get_session(request)
    plan_data = PLANS[plan]
    amount = plan_data["price"] * 100
    headers = {"Authorization": f"Bearer {PAYSTACK_LIVE_KEY}", "Content-Type": "application/json"}
    data = {
        "amount": amount, "email": f"{session_id}@truthguard.ai", "currency": "NGN",
        "channels": [method], "callback_url": "https://your-app.railway.app/verify",
        "metadata": {"session_id": session_id, "credits": plan_data["credits"]}
    }
    res = requests.post("https://api.paystack.co/transaction/initialize", headers=headers, json=data)
    response_data = res.json()
    if response_data["status"]:
        return RedirectResponse(url=response_data["data"]["authorization_url"], status_code=303)
    else:
        return RedirectResponse(url="/pricing", status_code=303)

@app.get("/verify")
async def verify(request: Request, reference: str):
    headers = {"Authorization": f"Bearer {PAYSTACK_LIVE_KEY}"}
    res = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)
    data = res.json()
    if data["status"] and data["data"]["status"] == "success":
        metadata = data["data"]["metadata"]
        session_id = metadata["session_id"]
        credits = int(metadata["credits"])
        global USERS
        USERS = load_users()
        USERS[session_id] = get_credits(session_id) + credits
        save_users(USERS)
    return RedirectResponse(url="/pricing", status_code=303)

@app.get("/download/{b64_data}")
async def download(b64_data: str):
    data = base64.b64decode(b64_data).decode()
    return StreamingResponse(io.StringIO(data), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=truthguard_cleaned.csv"})