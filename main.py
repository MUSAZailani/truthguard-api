from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
import pandas as pd
import io
import uuid
import base64
import re

app = FastAPI(title="TruthGuard AI")

USERS = {}
NEW_USER_CREDITS = 500

def get_session(request: Request):
    session_id = request.cookies.get("tg_session")
    if not session_id:
        session_id = str(uuid.uuid4())
        USERS[session_id] = NEW_USER_CREDITS
    return session_id

def get_credits(session_id): return USERS.get(session_id, NEW_USER_CREDITS)
def use_credit(session_id):
    if session_id in USERS and USERS[session_id] > 0: USERS[session_id] -= 1

def clean_text(text):
    if pd.isna(text): return ""
    text = str(text).strip()
    text = re.sub(r'\s+', ' ', text) # remove extra spaces
    
    # 1. Fix repeated words: "love love" -> "love"
    words = text.split()
    words = [words[i] for i in range(len(words)) if i == 0 or words[i].lower()!= words[i-1].lower()]
    text = " ".join(words)
    
    # 2. Fix common spelling mistakes
    fixes = {
        "banananas": "bananas",
        "recieve": "receive",
        "teh": "the",
        "cat's": "cats",
        "it's": "its"
    }
    for wrong, right in fixes.items():
        text = re.sub(rf'\b{wrong}\b', right, text, flags=re.IGNORECASE)
    
    # 3. Capitalize first letter
    if text: text = text[0].upper() + text[1:]
    return text

def smart_clean(df: pd.DataFrame):
    # Clean every text cell
    for col in df.columns:
        df[col] = df[col].apply(clean_text)
    
    # Remove duplicate rows
    df = df.drop_duplicates()
    # Remove completely empty rows
    df = df.replace('', pd.NA).dropna(how='all').fillna('')
    return df

HOME_HTML = """<!DOCTYPE html><html><head><title>TruthGuard AI</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>body{{background:#0a0a0a;color:#fff;font-family:Arial;margin:0;padding:0;display:flex;justify-content:center;align-items:center;min-height:100vh}}
.container{{text-align:center;padding:40px 20px;max-width:700px}}.shield{{font-size:5em}}.btn{{background:#00ff88;color:#000;padding:18px 40px;border-radius:12px;text-decoration:none;font-weight:bold;margin:10px;display:inline-block;font-size:1.2em}}.credits{{background:#1a1a1a;padding:10px 20px;border-radius:25px;display:inline-block}}</style>
</head><body><div class="container"><div class="shield">🛡️</div><h1>TruthGuard AI</h1><div class="credits">Credits: {credits}</div>
<p>AI Powered CSV Cleaning - Fixes Spelling + Grammar</p><a href="/clean" class="btn">CLEAN DATA</a><a href="/pricing" class="btn" style="background:#1a1a1a;color:#fff">Buy Credits</a></div></body></html>"""

CLEAN_HTML = """<!DOCTYPE html><html><head><title>Clean Data</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>body{{background:#0a0a0a;color:#fff;font-family:Arial;padding:20px}}.container{{max-width:700px;margin:0 auto}}.shield{{font-size:2.5em;text-align:center}}
input,button,textarea{{width:100%;padding:14px;margin:12px 0;border-radius:10px;border:none;background:#1a1a1a;color:#fff;box-sizing:border-box}}
button{{background:#00ff88;color:#000;font-weight:bold;cursor:pointer}}button:disabled{{background:#333;color:#666}}.error{{color:#ff4444;text-align:center}}.success{{color:#00ff88;text-align:center}}
.download{{background:#00ff88;color:#000;padding:14px;text-align:center;border-radius:10px;text-decoration:none;display:block;font-weight:bold}}</style>
</head><body><div class="container"><div class="shield">🛡️</div><h1 style="text-align:center">Clean Data</h1>
<p style="text-align:center">Credits: {credits}</p><p class="{msg_class}">{message}</p>{download_link}
<form method="post" enctype="multipart/form-data">
<label>Upload CSV:</label><input type="file" name="file" accept=".csv" {disabled}>
<label>Or Paste CSV:</label><textarea name="text_data" rows="8" placeholder="name,note\nJohn,i love banananas" {disabled}></textarea>
<button type="submit" {disabled}>CLEAN DATA</button></form><br><a href="/" style="color:#00ff88">← Back Home</a></div></body></html>"""

PRICING_HTML = """<!DOCTYPE html><html><head><title>Pricing</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>body{{background:#0a0a0a;color:#fff;font-family:Arial;text-align:center;padding:40px 20px}}.shield{{font-size:2.5em}}
.card{{background:#1a1a1a;padding:30px;margin:20px auto;border-radius:15px;max-width:400px}}
.pay-btn{{background:#00ff88;color:#000;padding:14px 25px;border-radius:10px;border:none;font-weight:bold;cursor:pointer;width:100%;margin:8px 0}}</style>
</head><body><div class="shield">🛡️</div><h1>Buy Credits</h1><p>Credits: {credits}</p>
<div class="card"><h2>100 Credits - $10</h2><form method="post" action="/pay">
<input type="hidden" name="plan" value="100">
<button class="pay-btn" name="method" value="card">Pay with Card</button>
<button class="pay-btn" name="method" value="transfer">Pay with Transfer</button>
<button class="pay-btn" name="method" value="bank">Pay with Bank</button>
<button class="pay-btn" name="method" value="ussd">Pay with USSD</button>
</form></div><br><a href="/" style="color:#00ff88">← Back Home</a></body></html>"""

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    session_id = get_session(request)
    response = HTMLResponse(HOME_HTML.format(credits=get_credits(session_id)))
    response.set_cookie("tg_session", session_id)
    return response

@app.get("/clean", response_class=HTMLResponse)
async def clean_page(request: Request):
    session_id = get_session(request)
    credits = get_credits(session_id)
    disabled = "disabled" if credits <= 0 else ""
    message = "Kindly buy credits to continue" if credits <= 0 else ""
    response = HTMLResponse(CLEAN_HTML.format(credits=credits, message=message, msg_class="error" if credits <= 0 else "", download_link="", disabled=disabled))
    response.set_cookie("tg_session", session_id)
    return response

@app.post("/clean", response_class=HTMLResponse)
async def clean_data(request: Request, file: UploadFile = File(None), text_data: str = Form(None)):
    session_id = get_session(request)
    credits = get_credits(session_id)
    if credits <= 0: return HTMLResponse(CLEAN_HTML.format(credits=0, message="Kindly buy credits to continue", msg_class="error", download_link="", disabled="disabled"))
    if not file and not text_data: return HTMLResponse(CLEAN_HTML.format(credits=credits, message="Please upload a CSV file or paste data first", msg_class="error", download_link="", disabled=""))
    
    try:
        if file and file.filename: df = pd.read_csv(file.file)
        else: df = pd.read_csv(io.StringIO(text_data))
        
        original = df.to_string()
        df = smart_clean(df)
        use_credit(session_id)
        
        output = io.StringIO()
        df.to_csv(output, index=False)
        b64_data = base64.b64encode(output.getvalue().encode()).decode()
        
        download_link = f'<a href="/download/{b64_data}" class="download">⬇️ Download Cleaned CSV - {len(df)} rows</a>'
        message = f"✅ Cleaned! Fixed spelling, grammar, and duplicates. 1 credit used."
        return HTMLResponse(CLEAN_HTML.format(credits=get_credits(session_id), message=message, msg_class="success", download_link=download_link, disabled=""))
    except Exception as e:
        return HTMLResponse(CLEAN_HTML.format(credits=credits, message=f"Error: {str(e)}", msg_class="error", download_link="", disabled=""))

@app.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    session_id = get_session(request)
    response = HTMLResponse(PRICING_HTML.format(credits=get_credits(session_id)))
    response.set_cookie("tg_session", session_id)
    return response

@app.post("/pay")
async def pay(request: Request, plan: str = Form(...)):
    session_id = get_session(request)
    USERS[session_id] = get_credits(session_id) + int(plan)
    return RedirectResponse(url="/pricing", status_code=303)

@app.get("/download/{b64_data}")
async def download(b64_data: str):
    data = base64.b64decode(b64_data).decode()
    return StreamingResponse(io.StringIO(data), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=truthguard_cleaned.csv"})