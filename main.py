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
        <title>TruthGuard AI v2.3</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: Arial; background: #0a0a0a; color: #fff; padding: 20px; text-align: center; }
            textarea { width: 90%; height: 200px; background: #1a1a1a; color: #fff; border: 1px solid #333; padding: 10px; border-radius: 8px; }
            button { background: #00FF88; color: #000; padding: 12px 20px; border: none; border-radius: 8px; font-weight: bold; margin-top: 10px; cursor: pointer; width: 90%; }
        </style>
    </head>
    <body>
        <h1>TruthGuard AI v2.3</h1>
        <p>Upload CSV or paste claims to verify</p>
        
        <textarea id="claims" placeholder="claim&#10;Nigeria is in Africa&#10;The moon is cheese"></textarea>
        <br>
        <button onclick="cleanData()">Clean My Data</button>
        
        <!-- PAYMENT BUTTON START -->
        <br><br>
        <button id="payBtn" style="background:#00C3FF;color:#000;padding:15px;border:none;border-radius:8px;font-weight:bold;width:90%;font-size:16px">
          Pay ₦10,000 for 1000 Claims
        </button>

        <script src="https://js.paystack.co/v1/inline.js"></script>
        <script>
          document.getElementById('payBtn').onclick = function() {
            PaystackPop.setup({
              key: 'pk_test_b89a61386411b3b47b79d402555417e1b333261c',
              email: 'test@example.com',
              amount: 1000000, // 10000 * 100 = kobo
              currency: 'NGN',
              ref: 'TG_' + Date.now(),
              callback: function(response){ 
                alert('Payment Successful! Ref: ' + response.reference + '\n\nWe will unlock 1000 claims for you'); 
              }
            }).openIframe();
          }
        </script>
        <!-- PAYMENT BUTTON END -->
        
        <p style="margin-top:20px">Example: claim<br>Nigeria is in Africa<br>The moon is cheese</p>
        <a href="/docs">API Docs</a>

        <script>
        function cleanData() {
            alert('Cleaning... Connect this to your API later');
        }
        </script>
    </body>
    </html>
    """)

@app.post("/batch-verify")
def batch_verify(req: BatchRequest, request: Request):
    log_visit(request.client.host, str(req.claims), "/batch-verify")
    return {"status": "received", "count": len(req.claims)}