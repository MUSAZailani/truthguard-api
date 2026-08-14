from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
import pandas as pd
import io
import uuid
import asyncio

app = FastAPI(title="TruthGuard AI")

USERS = {}
NEW_USER_CREDITS = 500
PAYSTACK_LIVE_KEY = "sk_live_YOUR_LIVE_KEY_HERE"

def get_session(request: Request):
    session_id = request.cookies.get("tg_session")
    if not session_id:
        session_id = str(uuid.uuid4())
        USERS[session_id] = NEW_USER_CREDITS
    return session_id

def get_credits(session_id):
    return USERS.get(session_id, NEW_USER_CREDITS)

def use_credit(session_id):
    if session_id in USERS and USERS[session_id] > 0:
        USERS[session_id] -= 1

async def smart_clean(df: pd.DataFrame):
    df = df.drop_duplicates()
    df = df.fillna("")
    return df

HOME_HTML = """<!DOCTYPE html><html><head><title>TruthGuard AI</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{{background:#0a0a0a;color:#fff;font-family:Arial;margin:0;padding:0;display:flex;justify-content:center;align-items:center;min-height:100vh}}
.container{{text-align:center;padding:40px 20px;max-width:700px}}
.shield{{font-size:5em;margin-bottom:10px}}
h1{{font-size:2.8em;margin:10px 0}}
p{{font-size:1.2em;color:#aaa;margin-bottom:30px}}
.btn{{background:#00ff88;color:#000;padding:18px 40px;border-radius:12px;text-decoration:none;font-weight:bold;margin:10px;display:inline-block;font-size:1.2em}}
.credits{{background:#1a1a1a;padding:10px 20px;border-radius:25px;display:inline-block;margin-bottom:20px;font-size:1.1em}}
</style>
</head><body>
<div class="container">
<div class="shield">🛡️</div>
<h1>TruthGuard AI</h1>
<div class="credits">Your Credits: {credits}</div>
<p>Clean 5000+ rows of messy CSVs with AI in seconds. Built for speed.</p>
<a href="/clean" class="btn">CLEAN DATA</a>
<a href="/pricing" class="btn" style="background:#1a1a1a;color:#fff">Buy Credits</a>
</div></body></html>"""

CLEAN_HTML = """<!DOCTYPE html><html><head><title>Clean Data - TruthGuard AI</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{{background:#0a0a0a;color:#fff;font-family:Arial;padding:20px}}
.container{{max-width:700px;margin:0 auto}}
.shield{{font-size:2.5em;text-align:center;margin-bottom:10px}}
input,button,textarea{{width:100%;padding:14px;margin:12px 0;border-radius:10px;border:none;background:#1a1a1a;color:#fff;box-sizing:border-box;font-size:1em}}
button{{background:#00ff88;color:#000;font-weight:bold;cursor:pointer;font-size:1.1em}}
button:disabled{{background:#333;color:#666;cursor:not-allowed}}
.error{{color:#ff4444;font-weight:bold;text-align:center}}
.success{{color:#00ff88;font-weight:bold;text-align:center}}
.download{{background:#00ff88;color:#000;padding:14px;text-align:center;border-radius:10px;text-decoration:none;display:block;font-weight:bold}}
</style>
</head><body><div class="container">
<div class="shield">🛡️</div>
<h1 style="text-align:center">Clean Data</h1>
<p style="text-align:center">Credits: {credits}</p>
<p class="{msg_class}">{message}</p>
{download_link}
<form method="post" enctype="multipart/form-data">
<label>Upload CSV:</label><input type="file" name="file" accept=".csv" {disabled}>
<label>Or Paste CSV:</label><textarea name="text_data" rows="8" placeholder="Paste 5000+ rows here" {disabled}></textarea>
<button type="submit" {disabled}>CLEAN DATA</button>
</form><br><a href="/" style="color:#00ff88">← Back Home</a></div></body></html>"""

PRICING_HTML = """<!DOCTYPE html><html><head><title>Pricing - TruthGuard AI</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{{background:#0a0a0a;color:#fff;font-family:Arial;text-align:center;padding:40px 20px}}
.shield{{font-size:2.5em}}
.card{{background:#1a1a1a;padding:30px;margin:20px auto;border-radius:15px;max-width:400px}}
.pay-btn{{background:#00ff88;color:#000;padding:14px 25px;border-radius:10px;border:none;font-weight:bold;cursor:pointer;width:100%;margin:8px 0;font-size:1em}}
</style>
</head><body>
<div class="shield">🛡️</div>
<h1>Buy Credits</h1>
<p>Credits: {credits}</p>
<div class="card">
<h2>100 Credits - $10</h2>
<form method="post" action="/pay">
<input type="hidden" name="plan" value="100">
<button class="pay-btn" name="method" value="card">Pay with Card</button>
<button class="pay-btn" name="method" value="transfer">Pay with Transfer</button>
<button class="pay-btn" name="method" value="bank">Pay with Bank</button>
<button class="pay-btn" name="method" value="ussd">Pay with USSD</button>
</form>
<p style="font-size:0.9em;color:#aaa">Secured by Paystack Live</p>
</div><br><a href="/" style="color:#00ff88">← Back Home</a></body></html>"""

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    session_id = get_session(request)
    credits = get_credits(session_id)
    response = HTMLResponse(HOME_HTML.format(credits=credits))
    response.set_cookie("tg_session", session_id)
    return response

@app.get("/clean", response_class=HTMLResponse)
async def clean_page(request: Request):
    session_id = get_session(request)
    credits = get_credits(session_id)
    disabled = "disabled" if credits <= 0 else ""
    message = "Kindly buy credits to continue" if credits <= 0 else ""
    msg_class = "error" if credits <= 0 else ""
    response = HTMLResponse(CLEAN_HTML.format(credits=credits, message=message, msg_class=msg_class, download_link="", disabled=disabled))
    response.set_cookie("tg_session", session_id)
    return response

@app.post("/clean", response_class=HTMLResponse)
async def clean_data(request: Request, file: UploadFile = File(None), text_data: str = Form(None)):
    session_id = get_session(request)
    credits = get_credits(session_id)
    
    if credits <= 0:
        return HTMLResponse(CLEAN_HTML.format(credits=0, message="Kindly buy credits to continue", msg_class="error", download_link="", disabled="disabled"))
    
    try:
        if file:
            df = pd.read_csv(file.file, low_memory=False)
        elif text_data:
            df = pd.read_csv(io.StringIO(text_data), low_memory=False)
        else:
            return HTMLResponse(CLEAN_HTML.format(credits=credits, message="Please upload file or paste data", msg_class="error", download_link="", disabled=""))
        
        df = await smart_clean(df)
        use_credit(session_id)
        credits = get_credits(session_id)
        
        output = io.StringIO()
        df.to_csv(output, index=False)
        
        download_link = f'<a href="/download?data={output.getvalue()}" class="download">⬇️ Download Cleaned CSV</a>'
        return HTMLResponse(CLEAN_HTML.format(credits=credits, message="✅ Cleaned successfully! 1 credit used.", msg_class="success", download_link=download_link, disabled=""))
    
    except Exception as e:
        return HTMLResponse(CLEAN_HTML.format(credits=credits, message=f"Error: {str(e)}", msg_class="error", download_link="", disabled=""))

@app.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    session_id = get_session(request)
    credits = get_credits(session_id)
    response = HTMLResponse(PRICING_HTML.format(credits=credits))
    response.set_cookie("tg_session", session_id)
    return response

@app.post("/pay")
async def pay(request: Request, plan: str = Form(...), method: str = Form(...)):
    session_id = get_session(request)
    USERS