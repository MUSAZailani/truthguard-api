import os
import requests
import json
import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="TruthGuard AI v2.4", version="2.4.0")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
VISITOR_LOG = "visitors.json"

class CleanRequest(BaseModel):
    data: str

def log_visit(ip: str, data: str):
    log_entry = {"time": datetime.datetime.now().isoformat(), "ip": ip, "data": data}
    try:
        with open(VISITOR_LOG, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except:
        pass

def clean_with_groq(text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    prompt = f"You are a data cleaning and fact-checking AI. Clean grammar, fix errors, and fact-check this. Return JSON with fields: original, cleaned, verdict, explanation.\n\nData: {text}"
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1}
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    return r.json()["choices"][0]["message"]["content"]

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(content="""
    <html>
    <head>
        <title>TruthGuard AI v2.4</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: Arial; background: #0a0a0a; color: #fff; padding: 20px; text-align: center; }
            textarea { width: 90%; height: 200px; background: #1a1a1a; color: #fff; border: 1px solid #333; padding: 10px; border-radius: 8px; font-size:16px }
         .btn { padding: 18px; border: none; border-radius: 12px; font-weight: bold; margin-top: 12px; cursor: pointer; width: 90%; font-size:18px }
         .green { background: #00FF88; color: #000; }
         .plan { background: #111; border: 2px solid #333; padding: 25px; border-radius: 12px; margin: 15px auto; width: 90%; }
         .plan h3 { margin: 0; color: #00C3FF; font-size:22px }
         .plan p { font-size:20px; margin:10px 0; }
         .popular { border: 2px solid #00FF88; }
         .badge { background:#00FF88; color:#000; padding:5px 10px; border-radius:20px; font-size:12px; font-weight:bold }
          #result { background:#1a1a1a; padding:15px; border-radius:8px; margin-top:20px; text-align:left; white-space:pre-wrap; display:none }
        </style>
    </head>
    <body>
        <h1>TruthGuard AI v2.4</h1>
        <p>AI-Powered Data Cleaning & Fact Checking</p>

        <textarea id="claims" placeholder="Paste your data here, one row per line"></textarea>
        <br>
        <button class="btn green" onclick="cleanData()">Clean My Data</button>
        
        <div id="result"></div>

        <h2 style="margin-top:30px">Choose Your Data Cleaning Plan</h2>
        <div class="plan"><h3>Starter</h3><p><b>₦7,500</b> for 500</p><button class="btn" style="background:#00C3FF;color:#000" onclick="pay(7500,500)">Pay ₦7,500</button></div>
        <div class="plan"><h3>Basic</h3><p><b>₦15,000</b> for 1,000</p><button class="btn" style="background:#00C3FF;color:#000" onclick="pay(15000,1000)">Pay ₦15,000</button></div>
        <div class="plan popular"><span class="badge">MOST POPULAR</span><h3>Growth</h3><p><b>₦75,000</b> for 10,000</p><button class="btn" style="background:#00FF88;color:#000" onclick="pay(75000,10000)">Pay ₦75,000</button></div>
        <div class="plan"><h3>Enterprise</h3><p><b>₦150,000</b> for 20,000</p><button class="btn" style="background:#00C3FF;color:#000" onclick="pay(150000,20000)">Pay ₦150,000</button></div>

        <script src="https://js.paystack.co/v1/inline.js"></script>
        <script>
        async function cleanData() {
            const data = document.getElementById('claims').value;
            if(!data) return alert('Paste some data first');
            document.getElementById('result').style.display = 'block';
            document.getElementById('result').innerText = 'Cleaning...';
            const res = await fetch('/clean', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({data:data})});
            const json = await res.json();
            document.getElementById('result').innerText = JSON.stringify(json, null, 2);
        }
        function pay(amount, claims) {
          var handler = PaystackPop.setup({
            key: 'pk_test_b89a61386411b3b47b79d402555417e1b333261c',
            email: 'test@example.com',
            amount: amount * 100,
            currency: 'NGN',
            ref: 'TG_' + Date.now(),
            callback: function(response){ alert('Payment Successful! ' + claims.toLocaleString() + ' credits. Ref: ' + response.reference); },
            onClose: function(){ alert('Payment cancelled'); }
          });
          handler.openIframe();
        }
        </script>
    </body>
    </html>
    """)

@app.post("/clean")
def clean(req: CleanRequest, request: Request):
    log_visit(request.client.host, req.data)
    try:
        result = clean_with_groq(req.data)
        return JSONResponse(content=json.loads(result))
    except Exception as e:
        return JSONResponse(content={"error": str(e)})