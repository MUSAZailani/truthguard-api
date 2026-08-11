import os
import requests
import json
import datetime
import csv
import io
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="TruthGuard AI v2.3", version="2.3.0")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
VISITOR_LOG = "visitors.json"

class BatchRequest(BaseModel):
    claims: list[str]

def log_visit(ip: str, claim: str, endpoint: str):
    log_entry = {"time": datetime.datetime.now().isoformat(), "ip": ip, "endpoint": endpoint, "claim": claim}
    try:
        with open(VISITOR_LOG, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except:
        pass

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(content="""
    <html>
    <head>
        <title>TruthGuard AI v2.3 - Data Cleaning</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: Arial; background: #0a0a0a; color: #fff; padding: 20px; text-align: center; }
            textarea { width: 90%; height: 200px; background: #1a1a1a; color: #fff; border: 1px solid #333; padding: 10px; border-radius: 8px; font-size:16px }
          .btn { padding: 18px; border: none; border-radius: 12px; font-weight: bold; margin-top: 12px; cursor: pointer; width: 90%; font-size:18px }
          .green { background: #00FF88; color: #000; }
          .plan { background: #111; border: 2px solid #333; padding: 25px; border-radius: 12px; margin: 15px auto; width: 90%; }
          .plan h3 { margin: 0; color: #00C3FF; font-size:22px }
          .plan p { font-size:20px; margin:10px 0; }
          .popular { border: 2px solid #00FF88; transform: scale(1.02); }
          .badge { background:#00FF88; color:#000; padding:5px 10px; border-radius:20px; font-size:12px; font-weight:bold }
        </style>
    </head>
    <body>
        <h1>TruthGuard AI v2.3</h1>
        <p>AI-Powered Data Cleaning & Fact Checking</p>

        <textarea id="claims" placeholder="Paste your data here, one row per line"></textarea>
        <br>
        <button class="btn green" onclick="cleanData()">Clean My Data</button>

        <h2 style="margin-top:30px">Choose Your Data Cleaning Plan</h2>

        <!-- PLAN 1: 500 -->
        <div class="plan">
          <h3>Starter</h3>
          <p><b>$5</b> for 500 Data Cleaning</p>
          <button class="btn" style="background:#00C3FF;color:#000" onclick="pay(5,500)">Pay $5</button>
        </div>

        <!-- PLAN 2: 1K -->
        <div class="plan">
          <h3>Basic</h3>
          <p><b>$10</b> for 1,000 Data Cleaning</p>
          <button class="btn" style="background:#00C3FF;color:#000" onclick="pay(10,1000)">Pay $10</button>
        </div>

        <!-- PLAN 3: 10K - MOST POPULAR -->
        <div class="plan popular">
          <span class="badge">MOST POPULAR</span>
          <h3>Growth</h3>
          <p><b>$50</b> for 10,000 Data Cleaning</p>
          <button class="btn" style="background:#00FF88;color:#000" onclick="pay(50,10000)">Pay $50</button>
        </div>

        <!-- PLAN 4: 20K -->
        <div class="plan">
          <h3>Enterprise</h3>
          <p><b>$100</b> for 20,000 Data Cleaning</p>
          <button class="btn" style="background:#00C3FF;color:#000" onclick="pay(100,20000)">Pay $100</button>
        </div>

        <script src="https://js.paystack.co/v1/inline.js"></script>
        <script>
        function pay(amount, claims) {
          var handler = PaystackPop.setup({
            key: 'pk_test_b89a61386411b3b47b79d402555417e1b333261c',
            email: 'test@example.com',
            amount: amount * 100, // Paystack uses cents. $50 = 5000
            currency: 'USD',
            ref: 'TG_' + Date.now(),
            callback: function(response){
              alert('Payment Successful! You bought ' + claims.toLocaleString() + ' data cleaning credits. Ref: ' + response.reference);
            },
            onClose: function(){ alert('Payment cancelled'); }
          });
          handler.openIframe();
        }
        function cleanData() {
            alert('Cleaning... Connect this to your API next');
        }
        </script>

        <p style="margin-top:20px"><a href="/docs" style="color:#00C3FF">API Docs</a></p>
    </body>
    </html>
    """)

@app.post("/batch-verify")
def batch_verify(req: BatchRequest, request: Request):
    log_visit(request.client.host, str(req.claims), "/batch-verify")
    return {"status": "received", "count": len(req.claims)}