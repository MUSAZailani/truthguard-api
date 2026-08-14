from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
import pandas as pd
import io
import uuid
import base64
import re
import json
import os

app = FastAPI(title="TruthGuard AI")

DB_FILE = "users.json"
NEW_USER_CREDITS = 500
PAYSTACK_LIVE_KEY = "sk_live_YOUR_LIVE_KEY_HERE"

def load_users():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return json.load(f)
    return {}

def save_users(users):
    with open(DB_FILE, "w") as f: json.dump(users, f)

USERS = load_users()

def get_session(request: Request):
    session_id = request.cookies.get("tg_session")
    if not session_id:
        session_id = str(uuid.uuid4())
        USERS[session_id] = NEW_USER_CREDITS
        save_users(USERS)
    return session_id

def get_credits(session_id): return USERS.get(session_id, NEW_USER_CREDITS)

def use_credits(session_id, amount):
    if session_id in USERS and USERS[session_id] >= amount: 
        USERS[session_id] -= amount
        save_users(USERS)
        return True
    return False

SPELL_DICT = {"banananas": "bananas", "recieve": "receive", "teh": "the"}

def clean_text(text):
    if pd.isna(text): return ""
    text = str(text).strip().lower()
    text = re.sub(r'\s+', ' ', text)
    words = text.split()
    words = [words[i] for i in range(len(words)) if i == 0 or words[i]!= words[i-1]]
    words = [SPELL_DICT.get(w, w) for w in words]
    text = " ".join(words)
    return text.capitalize()

def smart_clean(df: pd.DataFrame):
    df = df.astype(str).apply(lambda x: x.str.strip())
    for col in df.columns:
        df[col] = df[col].apply(clean_text)
    df = df.drop_duplicates()
    df = df.replace('nan', '').replace('', pd.NA).dropna(how='all').fillna('')
    return df

def NAVBAR(credits):
    return f"""<div style="background:#111;padding:15px 20px;border-bottom:2px solid #00ff88;position:sticky;top:0;z-index:100">
<div style="max-width:900px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap">
<div style="display:flex;align-items:center;gap:8px"><span style="font-size:1.8em">🛡️</span><b style="font-size:1.2em">TruthGuard AI</b></div>
<div style="display:flex;gap:20px;align-items:center;flex-wrap:wrap">
<a href="/" style="color:#fff;text-decoration:none;font-weight:bold">Home</a>
<a href="/clean" style="color:#fff;text-decoration:none;font-weight:bold">Clean Data</a>
<a href="/pricing" style="color:#fff;text-decoration:none;font-weight:bold">Pricing</a>
<div class="credits">Credits: {credits}</div>
</div></div></div>"""

CSS = """<style>body{background:#0a0a0a;color:#fff;font-family:Arial, sans-serif;margin:0;padding:0}
.container{max-width:800px;margin:0 auto;padding:30px 20px}.btn{background:#00ff88;color:#000;padding:16px 35px;border-radius:12px;text-decoration:none;font-weight:bold;display:inline-block;font-size:1.1em;border:none;cursor:pointer;width:100%;margin:8px 0}
.credits{background:#1a1a1a;padding:8px 18px;border-radius:25px;display:inline-block;font-size:0.95em;border:1px solid #333}
input,textarea{width:100%;padding:14px;margin:12px 0;border-radius:10px;border:1px solid #333;background:#1a1a1a;color:#fff;box-sizing:border-box}
.error{color:#ff4444;font-weight:bold;text-align:center;padding:10px;background:#2a0000;border-radius:8px}
.success{color:#00ff88;font-weight:bold;text-align:center;padding:10px;background:#002a00;border-radius:8px}
.download{background:#00ff88;color:#000;padding:14px;text-align:center;border-radius:10px;text-decoration:none;display:block;font-weight:bold;margin:15px 0}
.card{background:#1a1a1a;padding:25px;margin:15px auto;border-radius:15px}</style>"""

def HOME_PAGE(credits): return f"<!DOCTYPE html><html><head><title>TruthGuard AI</title><meta name=viewport content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{NAVBAR(credits)}<div class=container style=text-align:center><div style=font-size:4em;margin:20px 0>🛡️</div><h1>TruthGuard AI</h1><p style=color:#aaa;font-size:1.2em>AI Powered CSV Cleaning. Handles 5000+ rows instantly.</p><div style=margin-top:30px><a href=/clean class=btn>CLEAN DATA</a><a href=/pricing class=btn style=background:#1a1a1a;color:#fff>Buy Credits</a></div></div></body></html>"
def CLEAN_PAGE(credits, message="", msg_class="", download_link="", disabled=""): return f"<!DOCTYPE html><html><head><title>Clean Data - TruthGuard AI</title><meta name=viewport content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{NAVBAR(credits)}<div class=container><h1 style=text-align:center>Clean Data</h1><p class={msg_class}>{message}</p>{download_link}<form method=post enctype=multipart/form-data><label><b>Upload CSV/TXT:</b></label><input type=file name=file accept=.csv,.txt {disabled}><label><b>Or Paste Data:</b></label><textarea name=text_data rows=10 placeholder='Paste 5000 rows here...' {disabled}></textarea><button type=submit class=btn {disabled}>CLEAN DATA</button></form></div></body></html>"
def PRICING_PAGE(credits): return f"<!DOCTYPE html><html><head><title>Pricing - TruthGuard AI</title><meta name=viewport content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{NAVBAR(credits)}<div class=container><h1 style=text-align:center>Buy Credits</h1><div class=card><h2 style=text-align:center>100 Credits - $10</h2><p style=text-align:center;color:#aaa>1 Credit = 1 Row Cleaned</p><form method=post action=/pay><input type=hidden name=plan value=100><button class=btn name=method value=card>Pay with Card</button><button class=btn name=method value=transfer>Pay with Transfer</button><button class=btn name=method value=bank>Pay with Bank</button><button class=btn name=method value=ussd>Pay with USSD</button></form></div></div></body></html>"

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
    message = "Kindly buy credits to continue" if credits <= 0 else ""
    response = HTMLResponse(CLEAN_PAGE(credits, message, "error" if credits <= 0 else "", disabled))
    response.set_cookie("tg_session", session_id)
    return response

@app.post("/clean", response_class=HTMLResponse)
async def clean_data(request: Request, file: UploadFile = File(None), text_data: str = Form(None)):
    session_id = get_session(request)
    credits = get_credits(session_id)
    if credits <= 0: return HTMLResponse(CLEAN_PAGE(0, "Kindly buy credits to continue", "error", "", "disabled"))
    if not file and not text_data: return HTMLResponse(CLEAN_PAGE(credits, "Please upload a file or paste data first", "error", "", ""))
    try:
        if file and file.filename: df = pd.read_csv(file.file, header=None, names=["data"], on_bad_lines='skip')
        else: df = pd.read_csv(io.StringIO(text_data), header=None, names=["data"], on_bad_lines='skip')
        rows = len(df)
        if credits < rows: return HTMLResponse(CLEAN_PAGE(credits, f"Not enough credits. This will cost {rows} credits. You have {credits}.", "error", "", ""))
        df = smart_clean(df)
        use_credits(session_id, rows)
        output = io.StringIO()
        df.to_csv(output, index=False, header=False)
        b64_data = base64.b64encode(output.getvalue().encode()).decode()
        download_link = f'<a href="/download/{b64_data}" class="download">⬇️ Download Cleaned CSV - {len(df)} rows</a>'
        message = f"✅ Cleaned {rows} rows! {rows} Credits Used. You have {get_credits(session_id)} left."
        return HTMLResponse(CLEAN_PAGE(get_credits(session_id), message, "success", download_link, ""))
    except Exception as e: return HTMLResponse(CLEAN_PAGE(credits, f"Error: {str(e)}", "error", "", ""))

@app.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    session_id = get_session(request)
    response = HTMLResponse(PRICING_PAGE(get_credits(session_id)))
    response.set_cookie("tg_session", session_id)
    return response

@app.post("/pay")
async def pay(request: Request, plan: str = Form(...), method: str = Form(...)):
    session_id = get_session(request)
    USERS[session_id] = get_credits(session_id) + int(plan)
    save_users(USERS)
    return RedirectResponse(url="/pricing", status_code=303)

@app.get("/download/{b64_data}")
async def download(b64_data: str):
    data = base64.b64decode(b64_data).decode()
    return StreamingResponse(io.StringIO(data), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=truthguard_cleaned.csv"})