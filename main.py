from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="TruthGuard AI")
USER_CREDITS = 100

HOME_HTML = """<!DOCTYPE html><html><head><title>TruthGuard AI</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{{background:#0a0a0a;color:#fff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial;margin:0;padding:0;display:flex;justify-content:center;align-items:center;min-height:100vh}}
.container{{text-align:center;padding:40px 20px}}
h1{{font-size:2.5em;margin-bottom:10px}}
p{{font-size:1.1em;color:#aaa;margin-bottom:30px}}
.btn{{background:#00ff88;color:#000;padding:15px 30px;border-radius:12px;text-decoration:none;font-weight:bold;margin:10px;display:inline-block;font-size:1em;transition:0.2s}}
.btn:hover{{transform:scale(1.05)}}
.credits{{background:#1a1a1a;padding:8px 15px;border-radius:20px;display:inline-block;margin-bottom:20px}}
</style>
</head><body>
<div class="container">
<h1>🛡️ TruthGuard AI</h1>
<div class="credits">Credits: {credits}</div>
<p>Clean messy CSVs with AI in seconds</p>
<a href="/clean" class="btn">Start Cleaning</a>
<a href="/pricing" class="btn">Buy Credits</a>
</div></body></html>"""

CLEAN_HTML = """<!DOCTYPE html><html><head><title>Clean Data</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{{background:#0a0a0a;color:#fff;font-family:Arial;padding:20px}}
.container{{max-width:600px;margin:0 auto}}
input,button,textarea{{width:100%;padding:12px;margin:10px 0;border-radius:8px;border:none;background:#1a1a1a;color:#fff;box-sizing:border-box}}
button{{background:#00ff88;color:#000;font-weight:bold;cursor:pointer}}
a{{color:#00ff88}}
</style>
</head><body><div class="container">
<h1>Clean Your Data</h1>
<p>Credits: {credits}</p>
<p style="color:#00ff88">{error}</p>
<form method="post" enctype="multipart/form-data">
<label>Upload CSV:</label><input type="file" name="file">
<label>Or Paste CSV:</label><textarea name="text_data" rows="6" placeholder="Paste CSV here"></textarea>
<button type="submit">Clean Data - 1 Credit</button>
</form><br><a href="/">← Back Home</a></div></body></html>"""

PRICING_HTML = """<!DOCTYPE html><html><head><title>Pricing</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{{background:#0a0a0a;color:#fff;font-family:Arial;text-align:center;padding:40px 20px}}
.card{{background:#1a1a1a;padding:30px;margin:20px auto;border-radius:15px;max-width:300px}}
.btn{{background:#00ff88;color:#000;padding:12px 25px;border-radius:10px;border:none;font-weight:bold;cursor:pointer}}
</style>
</head><body>
<h1>Buy Credits</h1>
<p>Credits: {credits}</p>
<div class="card">
<h2>100 Credits</h2>
<p>$10</p>
<form method="post" action="/pay">
<button class="btn" name="plan" value="100">Buy Now</button>
</form></div><br><a href="/" style="color:#00ff88">← Back Home</a></body></html>"""

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