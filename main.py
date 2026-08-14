from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="TruthGuard AI")
USER_CREDITS = 100

HOME_HTML = """<!DOCTYPE html><html><head><title>TruthGuard AI</title>
<style>body{{background:#0a0a0a;color:#fff;font-family:Arial;text-align:center;padding:50px}}
.btn{{background:#00ff88;color:#000;padding:15px 30px;border-radius:8px;text-decoration:none;font-weight:bold;margin:5px}}</style>
</head><body><h1>🛡️ TruthGuard AI</h1><p>Clean messy CSVs with AI. Credits: {credits}</p>
<a href="/clean" class="btn">Start Cleaning</a> <a href="/pricing" class="btn">Buy Credits</a></body></html>"""

CLEAN_HTML = """<!DOCTYPE html><html><head><title>Clean Data</title>
<style>body{{background:#0a0a0a;color:#fff;font-family:Arial;padding:30px}}
input,button,textarea{{padding:10px;margin:5px;border-radius:5px}}</style>
</head><body><h1>Clean Your Data</h1><p>Credits: {credits}</p><p style="color:#00ff88">{error}</p>
<form method="post" enctype="multipart/form-data"><input type="file" name="file"><br>
<textarea name="text_data" rows="5" cols="40" placeholder="Paste CSV here"></textarea><br>
<button type="submit">Clean Data - 1 Credit</button></form><br><a href="/">Home</a></body></html>"""

PRICING_HTML = """<!DOCTYPE html><html><head><title>Pricing</title>
<style>body{{background:#0a0a0a;color:#fff;font-family:Arial;text-align:center;padding:30px}}
.card{{background:#1a1a1a;padding:20px;margin:10px;border-radius:10px;display:inline-block}}</style>
</head><body><h1>Buy Credits</h1><p>Credits: {credits}</p>
<div class="card"><h2>100 Credits</h2><p>$10</p>
<form method="post" action="/pay"><button name="plan" value="100">Buy</button></form></div><br><a href="/">Home</a></body></html>"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HOME_HTML.format(credits=USER_CREDITS)

@app.get("/clean", response_class=HTMLResponse)
async def clean_page():
    return CLEAN_HTML.format(credits=USER_CREDITS, error="")

@app.post("/clean", response_class=HTMLResponse)
async def clean_data(file: UploadFile = File(None), text_data: str = Form(None)):
    global USER_CREDITS
    if USER_CREDITS <= 0:
        return CLEAN_HTML.format(credits=USER_CREDITS, error="Kindly buy credits to continue")
    USER_CREDITS -= 1
    return CLEAN_HTML.format(credits=USER_CREDITS, error="✅ Cleaned successfully! 1 credit used.")

@app.get("/pricing", response_class=HTMLResponse)
async def pricing():
    return PRICING_HTML.format(credits=USER_CREDITS)

@app.post("/pay")
async def pay(plan: str = Form(...)):
    global USER_CREDITS
    USER_CREDITS += int(plan)
    return RedirectResponse(url="/pricing", status_code=303)