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

app = FastAPI(title="TruthGuard AI v4.2")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
PAYSTACK_PUBLIC_KEY = os.environ.get("PAYSTACK_PUBLIC_KEY", "pk_test_b89a61386411b3b47b79d402555417e1b333261c")

# IN-MEMORY STORAGE - will reset on Railway restart. Later we add database
USER_CREDITS = {"guest": 500} # Everyone starts with 500 free credits
lastResults = []

class CleanRequest(BaseModel):
    data: str
    user_id: str = "guest"

def parse_ai_response(text):
    try: return json.loads(text)
    except:
        objects = re.findall(r'\{.*?\}', text, re.DOTALL)
        results = []
        for obj_str in objects:
            try: results.append(json.loads(obj_str))
            except: continue
        return results if results else [{"original": text, "cleaned": "Parse Error", "verdict": "Error", "explanation": "Could not parse"}]

def clean_with_groq(text, user_id):
    global lastResults
    credits = USER_CREDITS.get(user_id, 0)

    lines = [l for l in text.split('\n') if l.strip()]
    if credits < len(lines):
        return [{"error": f"Not enough credits. You have {credits} but need {len(lines)}. Go to Pricing page."}]
    if not GROQ_API_KEY:
        return [{"error": "GROQ_API_KEY not set in Railway"}]

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    prompt = f"""Process each line. Return ONE JSON array. RULES: 'cleaned' MUST fix typos and be factually correct. 'verdict' = True, False, or Partially True. Format: [{{"original":"...", "cleaned":"...", "verdict":"...", "explanation":"..."}}] Lines: {text}"""
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "temperature": 0.0}

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=120)
        r.raise_for_status()
        ai_response = r.json()["choices"][0]["message"]["content"]
        results = parse_ai_response(ai_response)

        # Deduct credits
        USER_CREDITS[user_id] = credits - len(results)
        lastResults = results
        return results
    except Exception as e:
        return [{"error": f"AI Error: {str(e)}"}]

def get_nav(active, credits):
    return f"""
    <div class="nav">
        <a href="/" class="{'active' if active=='home' else ''}">Home</a>
        <a href="/pricing" class="{'active' if active=='pricing' else ''}">Pricing</a>
    </div>
    <div class="credit-bar"><h2>Free Credits Left: <span id="credits">{credits}</span></h2></div>
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
     .green { background: #00FF88; color: #000; }.blue { background: #00C3FF; color: #000; }.yellow { background:#FFC107;color:#000 }.purple { background:#A855F7;color:#fff }
     .plan { background: #111; border: 2px solid #333; padding: 25px; border-radius: 12px; margin: 15px auto; width: 90%; max-width:400px; text-align:left }
        #result { margin-top:20px; text-align:left; max-width:800px; margin-left:auto; margin-right:auto }
     .result-card { background:#1a1a1a; padding:15px; border-radius:8px; margin-bottom:15px; font-size:14px; line-height:1.6; border-left: 4px solid #00C3FF }
     .verdict-true { color:#00FF88; font-weight:bold }.verdict-false { color:#FF4444; font-weight:bold }.verdict-partial { color:#FFC107; font-weight:bold }
    </style>
    """

@app.get("/", response_class=HTMLResponse)
def home():
    credits = USER_CREDITS.get("guest", 0)
    return HTMLResponse(content=f"""
    <html><head><title>TruthGuard AI - Cleaner</title><meta name="viewport" content="width=device-width, initial-scale=1.0">{get_style()}</head>
    <body>
        {get_nav('home', credits)}
        <h1>TruthGuard<br>AI</h1>
        <p style="font-size:18px">Batch Data Cleaning +<br>Fact Checking for Enterprises</p>
        <p>You get 500 credits FREE to start. No card needed.</p>

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
            const res = await fetch('/clean', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{data:data, user_id:"guest"}})}});
            const jsonArray = await res.json();
            if(jsonArray[0] && jsonArray[0].error) {{ document.getElementById('result').innerHTML = `<p style="color:red">${{jsonArray[0].error}}</p>`; return; }}

            lastResults = jsonArray; localStorage.setItem('tg_results', JSON.stringify(jsonArray));
            let html = '';
            jsonArray.forEach(item => {{
                let verdictClass = item.verdict === 'True'? 'verdict-true' : item.verdict === 'False'? 'verdict-false' : 'verdict-partial';
                html += `<div class="result-card"><b>Original:</b> ${{item.original}}<br><br><b>Cleaned:</b> ${{item.cleaned}}<br><br><b>Verdict:</b> <span class="${{verdictClass}}">${{item.verdict}}</span><br><br><b>Explanation:</b> ${{item.explanation}}</div>`;
            }});
            document.getElementById('result').innerHTML = html;
            document.getElementById('credits').innerText = {credits} - jsonArray.length;
            document.getElementById('downloadBtn').style.display = 'block';
        }}
        function cleanData() {{ const data = document.getElementById('claims').value; if(!data) return alert('Paste some data first'); processAndDisplay(data); }}
        async function uploadCSV() {{ const file = document.getElementById('csvFile').files[0]; if(!file) return alert('Select a file'); const text = await file.text(); processAndDisplay(text); }}
        </script>
    </body></html>
    """)

@app.get("/pricing", response_class=HTMLResponse)
def pricing():
    credits = USER_CREDITS.get("guest", 0)
    return HTMLResponse(content=f"""
    <html><head><title>TruthGuard AI - Pricing</title><meta name="viewport" content="width=device-width, initial-scale=1.0">{get_style()}</head>
    <body>
        {get_nav('pricing', credits)}
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
            key: '{PAYSTACK_PUBLIC_KEY}', // Will auto-switch to pk_live_ when you paste it
            email: 'customer@example.com',
            amount: amountUSD * 100 * 1500, // $ to NGN
            currency: 'NGN',
            ref: 'TG_' + Date.now(),
            callback: function(response){{
                alert('Payment Successful! ' + credits.toLocaleString() + ' credits added. Ref: ' + response.reference);
                // SUGGESTION 2: Here we would call backend to add credits + send email
                fetch('/add_credits?credits=' + credits + '&ref=' + response.reference)
            }},
            onClose: function(){{ alert('Payment cancelled'); }}
          }});
          handler.openIframe();
        }}
        </script>
    </body></html>
    """)

@app.get("/add_credits")
def add_credits(credits: int, ref: str):
    USER_CREDITS["guest"] += credits
    # SUGGESTION 2: Send email here later
    print(f"Payment {ref} received. Added {credits} credits. Total: {USER_CREDITS['guest']}")
    return {"status": "success", "new_balance": USER_CREDITS["guest"]}

@app.get("/results", response_class=HTMLResponse)
def results_page():
    credits = USER_CREDITS.get("guest", 0)
    return HTMLResponse(content=f"""
    <html><head><title>TruthGuard AI - Download</title><meta name="viewport" content="width=device-width, initial-scale=1.0">{get_style()}</head>
    <body>
        {get_nav('home', credits)}
        <h1>Download Your Cleaned Data</h1>
        <p>Export your last cleaned batch</p>
        <button class="btn purple" onclick="downloadCleanOnly()">Download Clean Data Only</button>
        <button class="btn green" onclick="downloadCSV()">Download Full Report CSV</button>
        <button class="btn blue" onclick="downloadPDF()">Download PDF Report</button>
        <div id="result"></div>
        <script>
        const lastResults = JSON.parse(localStorage.getItem('tg_results') || '[]');
        if(lastResults.length > 0){{
            let html = '<h3>Preview Last 3 Results</h3>';
            lastResults.slice(0,3).forEach(item => {{ html += `<div class="result-card"><b>Original:</b> ${{item.original}}<br><b>Cleaned:</b> ${{item.cleaned}}</div>`; }});
            document.getElementById('result').innerHTML = html;
        }} else {{ document.getElementById('result').innerHTML = '<p>No cleaned data yet. Go to Home and clean first.</p>'; }}

        function downloadCleanOnly() {{
            if(lastResults.length === 0) return alert('No data to download');
            let csv = 'Cleaned_Data\\n';
            lastResults.forEach(r => {{ csv += `"${{r.cleaned}}"\\n`; }});
            const blob = new Blob([csv], {{type: 'text/csv'}}); const url = window.URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'truthguard_clean_only.csv'; a.click();
        }}

        function downloadCSV() {{
            if(lastResults.length === 0) return alert('No data to download');
            let csv = 'Original,Cleaned,Verdict,Explanation\\n';
            lastResults.forEach(r => {{ csv += `"${{r.original}}","${{r.cleaned}}","${{r.verdict}}","${{r.explanation}}"\\n`; }});
            const blob = new Blob([csv], {{type: 'text/csv'}}); const url = window.URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'truthguard_full_report.csv'; a.click();
        }}
        function downloadPDF() {{ window.location.href = '/download/pdf'; }}
        </script>
    </body></html>
    """)

@app.post("/clean")
def clean(req: CleanRequest):
    return JSONResponse(content=clean_with_groq(req.data, req.user_id))

@app.get("/download/pdf")
def download_pdf():
    if not lastResults: return JSONResponse({"error":"No data to export"})
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 18); p.drawString(100, 750, "TruthGuard AI Audit Report")
    y = 720
    for i, r in enumerate(lastResults[:30]):
        p.setFont("Helvetica", 10); p.drawString(50, y, f"{i+1}. {r['original'][:80]}"); y -= 15
        p.drawString(60, y, f"-> {r['cleaned'][:80]}"); y -= 20
        if y < 100: p.showPage(); y = 750
    p.save(); buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment;filename=TruthGuard_Report.pdf"})