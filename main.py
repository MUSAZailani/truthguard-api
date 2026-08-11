import os
import requests
import json
import re
import csv
import io
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

app = FastAPI(title="TruthGuard AI v4.0")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
CREDITS = 1000
lastResults = []

class CleanRequest(BaseModel):
    data: str

def parse_ai_response(text):
    try: return json.loads(text)
    except:
        objects = re.findall(r'\{.*?\}', text, re.DOTALL)
        results = []
        for obj_str in objects:
            try: results.append(json.loads(obj_str))
            except: continue
        return results if results else [{"original": text, "cleaned": "Parse Error", "verdict": "Error", "explanation": "Could not parse"}]

def clean_with_groq(text):
    global CREDITS, lastResults
    if CREDITS <= 0: return [{"error": "No credits left. Please buy more on Pricing page."}]
    if not GROQ_API_KEY: return [{"error": "GROQ_API_KEY not set in Railway"}]

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    prompt = f"""Process each line. Return ONE JSON array. RULES: 'cleaned' MUST fix typos and be factually correct. 'verdict' = True, False, or Partially True. Format: [{{"original":"...", "cleaned":"...", "verdict":"...", "explanation":"..."}}] Lines: {text}"""
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "temperature": 0.0}
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    ai_response = r.json()["choices"][0]["message"]["content"]
    results = parse_ai_response(ai_response)
    CREDITS -= len(results)
    lastResults = results
    return results

def get_nav(active):
    return f"""
    <div class="nav">
        <a href="/" class="{'active' if active=='home' else ''}">Home</a>
        <a href="/pricing" class="{'active' if active=='pricing' else ''}">Pricing</a>
    </div>
    """

def get_style():
    return """
    <style>
        body { font-family: Arial; background: #0a0a0a; color: #fff; padding: 20px; text-align: center; }
       .nav { display:flex; justify-content:center; gap:40px; margin-bottom:20px; border-bottom:2px solid #00FF88; padding-bottom:10px }
       .nav a { color:#888; text-decoration:none; font-weight:bold; font-size:18px }
       .nav a.active { color:#00FF88 }
        h1 { color:#00FF88; font-size:42px; margin:10px 0 }
       .credit-bar { background:#111; padding:15px; border-radius:12px; margin:20px auto; border:2px solid #00FF88; max-width:400px }
       .credit-bar h2 { color:#00FF88; margin:0 }
        textarea { width: 90%; height: 150px; background: #1a1a1a; color: #fff; border: 1px solid #333; padding: 10px; border-radius: 8px; font-size:16px; max-width:600px }
       .btn { padding: 18px; border: none; border-radius: 12px; font-weight: bold; margin: 8px; cursor: pointer; width: 90%; font-size:18px; max-width:400px }
       .green { background: #00FF88; color: #000; }.blue { background: #00C3FF; color: #000; }.yellow { background:#FFC107;color:#000 }
       .plan { background: #111; border: 2px solid #333; padding: 25px; border-radius: 12px; margin: 15px auto; width: 90%; max-width:400px; text-align:left }
        #result { margin-top:20px; text-align:left; max-width:800px; margin-left:auto; margin-right:auto }
       .result-card { background:#1a1a1a; padding:15px; border-radius:8px; margin-bottom:15px; font-size:14px; line-height:1.6; border-left: 4px solid #00C3FF }
       .verdict-true { color:#00FF88; font-weight:bold }.verdict-false { color:#FF4444; font-weight:bold }.verdict-partial { color:#FFC107; font-weight:bold }
    </style>
    """

# PAGE 1: HOME / CLEANER
@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(content=f"""
    <html><head><title>TruthGuard AI - Cleaner</title><meta name="viewport" content="width=device-width, initial-scale=1.0">{get_style()}</head>
    <body>
        {get_nav('home')}
        <h1>TruthGuard<br>AI</h1>
        <p style="font-size:18px">Batch Data Cleaning +<br>Fact Checking for Enterprises</p>
        <p>Upload 1000s of rows. Fix typos.<br>Verify facts. Export clean data.</p>
        <div class="credit-bar"><h2>Credits Left: <span id="credits">{CREDITS}</span></h2></div>

        <h3>Paste Data or Upload CSV</h3>
        <textarea id="claims" placeholder="Paste multiple claims. One per line."></textarea><br>
        <input type="file" id="csvFile" accept=".csv,.txt" style="margin:10px; color:#fff"><br>
        <button class="btn green" onclick="cleanData()">Start Cleaning Data</button>
        <button class="btn blue" onclick="uploadCSV()">Upload & Clean CSV</button>

        <div id="result"></div>
        <button class="btn yellow" onclick="window.location.href='/results'" style="display:none" id="downloadBtn">Go To Download Page</button>

        <script>
        let lastResults = [];
        async function processAndDisplay(data) {{
            document.getElementById('result').innerHTML = '<p>Cleaning with AI... Please wait</p>';
            const res = await fetch('/clean', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{data:data}})}});
            const jsonArray = await res.json();
            lastResults = jsonArray; localStorage.setItem('tg_results', JSON.stringify(jsonArray));
            let html = '';
            jsonArray.forEach(item => {{
                if(item.error) {{ html = `<p style="color:red">${{item.error}}</p>`; return; }}
                let verdictClass = item.verdict === 'True'? 'verdict-true' : item.verdict === 'False'? 'verdict-false' : 'verdict-partial';
                html += `<div class="result-card"><b>Original:</b> ${{item.original}}<br><br><b>Cleaned:</b> ${{item.cleaned}}<br><br><b>Verdict:</b> <span class="${{verdictClass}}">${{item.verdict}}</span><br><br><b>Explanation:</b> ${{item.explanation}}</div>`;
            }});
            document.getElementById('result').innerHTML = html;
            document.getElementById('credits').innerText = {CREDITS} - jsonArray.length;
            document.getElementById('downloadBtn').style.display = 'block';
        }}
        function cleanData() {{ const data = document.getElementById('claims').value; if(!data) return alert('Paste some data first'); processAndDisplay(data); }}
        async function uploadCSV() {{ const file = document.getElementById('csvFile').files[0]; if(!file) return alert('Select a file'); const text = await file.text(); processAndDisplay(text); }}
        </script>
    </body></html>
    """)

# PAGE 2: PRICING
@app.get("/pricing", response_class=HTMLResponse)
def pricing():
    return HTMLResponse(content=f"""
    <html><head><title>TruthGuard AI - Pricing</title><meta name="viewport" content="width=device-width, initial-scale=1.0">{get_style()}</head>
    <body>
        {get_nav('pricing')}
        <h1>Buy More Credits</h1>
        <p>Choose a plan to continue cleaning data</p>

        <div class="plan"><h3>500 Data Cleaning</h3><p><b>$5</b> or <b>₦7,500</b></p><button class="btn blue" onclick="pay(5,500)">Pay $5</button></div>
        <div class="plan"><h3>1,000 Data Cleaning</h3><p><b>$10</b> or <b>₦15,000</b></p><button class="btn blue" onclick="pay(10,1000)">Pay $10</button></div>
        <div class="plan"><h3>10,000 Data Cleaning</h3><p><b>$50</b> or <b>₦75,000</b></p><button class="btn green" onclick="pay(50,10000)">Pay $50</button></div>
        <div class="plan"><h3>20,000 Data Cleaning</h3><p><b>$100</b> or <b>₦150,000</b></p><button class="btn green" onclick="pay(100,20000)">Pay $100</button></div>

        <script src="https://js.paystack.co/v1/inline.js"></script>
        <script>
        function pay(amountUSD, credits) {{
          var handler = PaystackPop.setup({{
            key: 'pk_test_b89a61386411b3b47b79d402555417e1b333261c',
            email: 'customer@example.com', amount: amountUSD * 100 * 1500, // Convert to NGN approx
            currency: 'NGN', ref: 'TG_' + Date.now(),
            callback: function(response){{ alert('Payment Successful! ' + credits.toLocaleString() + ' credits added. Ref: ' + response.reference); }},
            onClose: function(){{ alert('Payment cancelled'); }}
          }});
          handler.openIframe();
        }}
        </script>
    </body></html>
    """)

# PAGE 3: RESULTS / DOWNLOAD
@app.get("/results", response_class=HTMLResponse)
def results_page():
    return HTMLResponse(content=f"""
    <html><head><title>TruthGuard AI - Download</title><meta name="viewport" content="width=device-width, initial-scale=1.0">{get_style()}</head>
    <body>
        {get_nav('home')}
        <h1>Download Your Cleaned Data</h1>
        <p>Export your last cleaned batch</p>
        <button class="btn green" onclick="downloadCSV()">Download CSV</button>
        <button class="btn blue" onclick="downloadPDF()">Download PDF Report</button>
        <div id="result"></div>
        <script>
        const lastResults = JSON.parse(localStorage.getItem('tg_results') || '[]');
        if(lastResults.length > 0){{
            let html = '<h3>Preview Last 3 Results</h3>';
            lastResults.slice(0,3).forEach(item => {{ html += `<div class="result-card"><b>Original:</b> ${{item.original}}<br><b>Cleaned:</b> ${{item.cleaned}}</div>`; }});
            document.getElementById('result').innerHTML = html;
        }} else {{ document.getElementById('result').innerHTML = '<p>No cleaned data yet. Go to Home and clean first.</p>'; }}

        function downloadCSV() {{
            if(lastResults.length === 0) return alert('No data to download');
            let csv = 'Original,Cleaned,Verdict,Explanation\\n';
            lastResults.forEach(r => {{ csv += `"${{r.original}}","${{r.cleaned}}","${{r.verdict}}","${{r.explanation}}"\\n`; }});
            const blob = new Blob([csv], {{type: 'text/csv'}}); const url = window.URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'truthguard_results.csv'; a.click();
        }}
        function downloadPDF() {{ window.location.href = '/download/pdf'; }}
        </script>
    </body></html>
    """)

# API ENDPOINTS
@app.post("/clean")
def clean(req: CleanRequest):
    try: return JSONResponse(content=clean_with_groq(req.data))
    except Exception as e: return JSONResponse(content=[{"original": req.data, "cleaned": "", "verdict": "Error", "explanation": str(e)}])

@app.get("/download/pdf")
def download_pdf():
    if not lastResults: return JSONResponse({"error":"No data to export"})
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 18); p.drawString(100, 750, "TruthGuard AI Audit Report")
    y = 720
    for i, r in enumerate(lastResults[:30]): # max 30 rows in PDF
        p.setFont("Helvetica", 10); p.drawString(50, y, f"{i+1}. {r['original'][:80]}"); y -= 15
        p.drawString(60, y, f"-> {r['cleaned'][:80]}"); y -= 20
        if y < 100: p.showPage(); y = 750
    p.save(); buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment;filename=TruthGuard_Report.pdf"})