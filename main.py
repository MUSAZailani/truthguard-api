import os
import requests
import json
import re
import csv
import io
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="TruthGuard AI v3.1", version="3.1.0")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
CREDITS = 1000 # Start with 1000 free credits for testing
lastResults = [] # store last results for CSV download

class CleanRequest(BaseModel):
    data: str

def parse_ai_response(text):
    try:
        return json.loads(text)
    except:
        objects = re.findall(r'\{.*?\}', text, re.DOTALL)
        results = []
        for obj_str in objects:
            try: results.append(json.loads(obj_str))
            except: continue
        return results if results else [{"original": text, "cleaned": "Parse Error", "verdict": "Error", "explanation": "Could not parse"}]

def clean_with_groq(text):
    global CREDITS, lastResults
    if CREDITS <= 0: return [{"error": "No credits left. Please buy more."}]
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    prompt = f"""Process each line. Return ONE JSON array.
    RULES: 'cleaned' MUST be factually correct and fix typos. 'verdict' = True, False, or Partially True
    Format: [{{"original":"...", "cleaned":"...", "verdict":"...", "explanation":"..."}}]
    Lines: {text}"""
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "temperature": 0.0}
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    ai_response = r.json()["choices"][0]["message"]["content"]
    results = parse_ai_response(ai_response)
    CREDITS -= len(results)
    lastResults = results
    return results

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(content=f"""
    <html>
    <head>
        <title>TruthGuard AI v3.1</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: Arial; background: #0a0a0a; color: #fff; padding: 20px; text-align: center; }}
           .nav {{ display:flex; justify-content:center; gap:40px; margin-bottom:20px; border-bottom:2px solid #00FF88; padding-bottom:10px }}
           .nav a {{ color:#fff; text-decoration:none; font-weight:bold; font-size:18px }}
           .nav a.active {{ color:#00FF88 }}
            h1 {{ color:#00FF88; font-size:42px; margin:10px 0 }}
          .credit-bar {{ background:#111; padding:15px; border-radius:12px; margin:20px auto; border:2px solid #00FF88; max-width:400px }}
          .credit-bar h2 {{ color:#00FF88; margin:0 }}
            textarea {{ width: 90%; height: 150px; background: #1a1a1a; color: #fff; border: 1px solid #333; padding: 10px; border-radius: 8px; font-size:16px }}
          .btn {{ padding: 18px; border: none; border-radius: 12px; font-weight: bold; margin: 8px; cursor: pointer; width: 90%; font-size:18px; max-width:400px }}
          .green {{ background: #00FF88; color: #000; }}.blue {{ background: #00C3FF; color: #000; }}
          .plan {{ background: #111; border: 2px solid #333; padding: 25px; border-radius: 12px; margin: 15px auto; width: 90%; max-width:400px }}
            #result {{ margin-top:20px; text-align:left; max-width:800px; margin-left:auto; margin-right:auto }}
          .result-card {{ background:#1a1a1a; padding:15px; border-radius:8px; margin-bottom:15px; font-size:14px; line-height:1.6; border-left: 4px solid #00C3FF }}
          .verdict-true {{ color:#00FF88; font-weight:bold }}.verdict-false {{ color:#FF4444; font-weight:bold }}.verdict-partial {{ color:#FFC107; font-weight:bold }}
        </style>
    </head>
    <body>
        <div class="nav">
            <a href="#" class="active">Home</a>
            <a href="#">Data Cleaner</a>
            <a href="#">Pricing</a>
        </div>
        <h1>TruthGuard<br>AI</h1>
        <p style="font-size:18px">Batch Data Cleaning +<br>Fact Checking for Enterprises</p>
        <p>Upload 1000s of rows. Fix typos.<br>Verify facts. Export clean data.</p>

        <div class="credit-bar"><h2>Credits Left: <span id="credits">{CREDITS}</span></h2></div>

        <button class="btn green" onclick="document.getElementById('dataSection').scrollIntoView()">Start Cleaning Data</button>
        <button class="btn blue" onclick="document.getElementById('pricing').scrollIntoView()">View Pricing</button>

        <div id="dataSection" style="margin-top:40px">
            <h3>Option 1: Paste Data</h3>
            <textarea id="claims" placeholder="Paste multiple claims. One per line."></textarea>
            <br>
            <button class="btn green" onclick="cleanData()">Clean Text</button>

            <h3>Option 2: Upload CSV</h3>
            <input type="file" id="csvFile" accept=".csv,.txt" style="margin:10px; color:#fff">
            <button class="btn blue" onclick="uploadCSV()">Upload & Clean CSV</button>
            <button class="btn" style="background:#FFC107;color:#000" onclick="downloadCSV()">Download Results CSV</button>
        </div>

        <div id="result"></div>

        <div id="pricing" style="margin-top:40px">
            <h2>Buy More Credits</h2>
            <div class="plan"><h3>Starter</h3><p><b>₦7,500</b> for 500 credits</p><button class="btn" style="background:#00C3FF;color:#000" onclick="pay(7500,500)">Pay ₦7,500</button></div>
            <div class="plan"><h3>Growth</h3><p><b>₦75,000</b> for 10,000 credits</p><button class="btn" style="background:#00FF88;color:#000" onclick="pay(75000,10000)">Pay ₦75,000</button></div>
        </div>

        <script src="https://js.paystack.co/v1/inline.js"></script>
        <script>
        let lastResults = [];
        async function cleanData() {{
            const data = document.getElementById('claims').value;
            if(!data) return alert('Paste some data first');
            await processAndDisplay(data);
        }}
        async function uploadCSV() {{
            const file = document.getElementById('csvFile').files[0];
            if(!file) return alert('Select a file');
            const text = await file.text();
            await processAndDisplay(text);
        }}
        async function processAndDisplay(data) {{
            document.getElementById('result').innerHTML = '<p>Cleaning with AI... This may take 1-2 mins for large files</p>';
            const res = await fetch('/clean', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{data:data}})}});
            const jsonArray = await res.json();
            lastResults = jsonArray;
            let html = '';
            jsonArray.forEach(item => {{
                if(item.error) {{ html = `<p style="color:red">${{item.error}}</p>`; return; }}
                let verdictClass = item.verdict === 'True'? 'verdict-true' : item.verdict === 'False'? 'verdict-false' : 'verdict-partial';
                html += `<div class="result-card">
                    <b>Original:</b> ${{item.original}}<br><br>
                    <b>Cleaned:</b> ${{item.cleaned}}<br><br>
                    <b>Verdict:</b> <span class="${{verdictClass}}">${{item.verdict}}</span><br><br>
                    <b>Explanation:</b> ${{item.explanation}}
                </div>`;
            }});
            document.getElementById('result').innerHTML = html;
            document.getElementById('credits').innerText = {CREDITS} - jsonArray.length;
        }}
        function downloadCSV() {{
            if(lastResults.length === 0) return alert('Clean some data first');
            let csv = 'Original,Cleaned,Verdict,Explanation\\n';
            lastResults.forEach(r => {{
                csv += `"${{r.original}}","${{r.cleaned}}","${{r.verdict}}","${{r.explanation}}"\\n`;
            }});
            const blob = new Blob([csv], {{type: 'text/csv'}});
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a'); a.href = url; a.download = 'truthguard_results.csv'; a.click();
        }}
        function pay(amount, credits) {{
          var handler = PaystackPop.setup({{
            key: 'pk_test_b89a61386411b3b47b79d402555417e1b333261c',
            email: 'customer@example.com',
            amount: amount * 100,
            currency: 'NGN',
            ref: 'TG_' + Date.now(),
            callback: function(response){{ 
                alert('Payment Successful! ' + credits.toLocaleString() + ' credits added. Ref: ' + response.reference);
                location.reload();
            }},
            onClose: function(){{ alert('Payment cancelled'); }}
          }});
          handler.openIframe();
        }}
        </script>
    </body>
    </html>
    """)

@app.post("/clean")
def clean(req: CleanRequest, request: Request):
    try:
        result = clean_with_groq(req.data)
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content=[{"original": req.data, "cleaned": "", "verdict": "Error", "explanation": str(e)}])