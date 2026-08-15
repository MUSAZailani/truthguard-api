from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import pandas as pd
import io
import uuid
import base64
import re
import json
import os
import requests

app = FastAPI(title="TruthGuard AI")
templates = Jinja2Templates(directory="templates") # USE FOLDER

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
    with open(DB_FILE, "w") as f: json.dump(users, f)

USERS = load_users()

def get_session(request: Request):
    session_id = request.cookies.get("tg_session")
    if not session_id: session_id = str(uuid.uuid4())
    if session_id not in USERS:
        USERS[session_id] = NEW_USER_CREDITS
        save_users(USERS)
    return session_id

def get_credits(session_id): return load_users().get(session_id, NEW_USER_CREDITS)
def use_credits(session_id, amount):
    global USERS
    USERS = load_users()
    if USERS[session_id] >= amount:
        USERS[session_id] -= amount
        save_users(USERS)
        return True
    return False

SPELL_DICT = {"banananas": "bananas", "recieve": "receive", "teh": "the", "adress": "address", "seperate": "separate"}
def clean_text(text):
    if pd.isna(text): return ""
    text = str(text).strip().lower()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s*:\s*', ': ', text)
    words = text.split()
    cleaned_words = [SPELL_DICT.get(w.replace(':',''), w) for w in words]
    final_words = [cleaned_words[i] for i in range(len(cleaned_words)) if i == 0 or cleaned_words[i]!= cleaned_words[i-1]]
    return " ".join(final_words).strip()

def normalize_for_fingerprint(text):
    text = text.lower().strip()
    text = re.sub(r'^(address|phone|name|price|date|amount|ref|order|city|state|country|product|qty|total|note)\s*:?\s*', '', text)
    text = re.sub(r'\s*@\s*', '@', text)
    digits = re.sub(r'\D', '', text)
    if len(digits) >= 6: return digits
    return re.sub(r'[\$\,]', '', text)

def smart_clean(df: pd.DataFrame):
    df = df.astype(str)
    for col in df.columns: df[col] = df[col].apply(clean_text)
    df = df[~df['data'].isin(['', 'nan', 'none', 'null', 'n/a', 'data', 'na'])]
    df = df[df['data'].str.len() > 2]
    df['normalized'] = df['data'].apply(normalize_for_fingerprint)
    df['fingerprint'] = df['normalized'].str.replace(r'[^a-z0-9@]', '', regex=True)
    df = df.drop_duplicates(subset=['fingerprint'], keep='first')
    return df.drop(columns=['normalized', 'fingerprint'])

def NAVBAR(credits):
    return f"""<div style="background:#0d0d0d;padding:15px;border-bottom:2px solid #00ff88"><div style="max-width:900px;margin:0 auto;display:flex;justify-content:space-between"><b style="color:#00ff88">🛡️ TruthGuard AI</b><div>Credits: {credits}</div></div></div>"""
CSS = """<style>body{background:#0a0a0a;color:#e0e0e0;font-family:Arial;margin:0}.container{max-width:1000px;margin:0 auto;padding:30px 20px}.btn{background:#00ff88;color:#000;padding:16px;border-radius:10px;text-decoration:none;font-weight:bold;display:block;text-align:center;margin:8px 0} input,textarea{width:100%;padding:14px;margin:12px 0;border-radius:10px;border:1px solid #333;background:#111;color:#fff}.error{color:#ff4444;background:#1a0000;padding:12px;border-radius:8px}.success{color:#00ff88;background:#001a00;padding:12px;border-radius:8px}.download{background:#00ff88;color:#000;padding:14px;text-align:center;border-radius:10px;text-decoration:none;display:block;font-weight:bold}</style>"""

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    session_id = get_session(request)
    html = f"<!DOCTYPE html><html><head><title>TruthGuard AI</title><meta name=viewport content='width=device-width'>{CSS}</head><body>{NAVBAR(get_credits(session_id))}<div class=container style=text-align:center><h1 style=color:#00ff88>TruthGuard AI</h1><p>AI Powered CSV Cleaning</p><p style=color:#00ff88>New Users Get {NEW_USER_CREDITS} Free Credits</p><a href=/clean class=btn>CLEAN DATA</a><a href=/pricing class=btn>PRICING</a></div></body></html>"
    response = HTMLResponse(html)
    response.set_cookie("tg_session", session_id)
    return response

@app.get("/clean", response_class=HTMLResponse)
async def clean_page(request: Request):
    session_id = get_session(request)
    credits = get_credits(session_id)
    disabled = "disabled" if credits <= 0 else ""
    message = "kindly buy credits to continue" if credits <= 0 else ""
    html = f"<!DOCTYPE html><html><head><title>Cleaning</title><meta name=viewport content='width=device-width'>{CSS}</head><body>{NAVBAR(credits)}<div class=container><h1 style=color:#00ff88;text-align:center>Cleaning</h1><p class=error>{message}</p><form method=post enctype=multipart/form-data><label><b>Upload CSV/TXT:</b></label><input type=file name=file accept=.csv,.txt {disabled}><label><b>Or Paste Data:</b></label><textarea name=text_data rows=12 {disabled}></textarea><button type=submit class=btn {disabled}>CLEAN DATA</button></form></div></body></html>"
    response = HTMLResponse(html)
    response.set_cookie("tg_session", session_id)
    return response

@app.post("/clean", response_class=HTMLResponse)
async def clean_data(request: Request, file: UploadFile = File(None), text_data: str = Form(None)):
    session_id = get_session(request)
    credits = get_credits(session_id)
    if credits <= 0: return HTMLResponse("No credits")
    if file and file.filename: df = pd.read_csv(file.file, header=None, names=["data"], on_bad_lines='skip')
    else: df = pd.read_csv(io.StringIO(text_data), header=None, names=["data"], on_bad_lines='skip')
    rows = len(df)
    if credits < rows: return HTMLResponse(f"Not enough credits. Need {rows}")
    df_cleaned = smart_clean(df)
    use_credits(session_id, rows)
    output = io.StringIO()
    df_cleaned.to_csv(output, index=False, header=False)
    b64_data = base64.b64encode(output.getvalue().encode()).decode()
    html = f"<!DOCTYPE html><html><body>{NAVBAR(get_credits(session_id))}<div class=container><p class=success>Cleaned {rows} rows!</p><a href='/download/{b64_data}' class=download>Download</a></div></body></html>"
    return HTMLResponse(html)

@app.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    session_id = get_session(request)
    cards = "".join([f"<div style='border:2px solid #333;padding:20px;border-radius:15px;text-align:center'><h2>{p['name']}</h2><h1 style=color:#00ff88>₦{p['price']:,}</h1><p>{p['credits']:,} Credits</p><a href=/checkout/{k} class=btn>Buy</a></div>" for k,p in PLANS.items()])
    html = f"<!DOCTYPE html><html><head><title>Pricing</title><meta name=viewport content='width=device-width'>{CSS}</head><body>{NAVBAR(get_credits(session_id))}<div class=container><h1 style=text-align:center;color:#00ff88>Pricing</h1><div style='display:grid;grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));gap:20px'>{cards}</div></div></body></html>"
    response = HTMLResponse(html)
    response.set_cookie("tg_session", session_id)
    return response

@app.get("/download/{b64_data}")
async def download(b64_data: str):
    data = base64.b64decode(b64_data).decode()
    return StreamingResponse(io.StringIO(data), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=truthguard_cleaned.csv"})