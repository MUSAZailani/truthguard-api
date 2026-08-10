import os
import requests
import json
import datetime
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(
    title="TruthGuard AI v2.0",
    description="The Default Data Cleaning Layer for AI Companies. Batch fact-check 1000s of claims.",
    version="2.0.0",
    contact={"name": "Musa Zailani", "email": "zailaniheman@gmail.com"}
)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
VISITOR_LOG = "visitors.json"

class ClaimRequest(BaseModel):
    claim: str

class BatchRequest(BaseModel):
    claims: list[str]

def log_visit(ip: str, claim: str, endpoint: str):
    log_entry = {
        "time": datetime.datetime.now().isoformat(),
        "ip": ip,
        "endpoint": endpoint,
        "claim": claim
    }
    try:
        with open(VISITOR_LOG, "r") as f:
            logs = json.load(f)
    except:
        logs = []
    logs.append(log_entry)
    with open(VISITOR_LOG, "w") as f:
        json.dump(logs, f, indent=2)

async def fact_check_single(claim: str):
    """Check 1 claim - used by batch too"""
    prompt = f"You are a data cleaner. Claim: '{claim}'. Respond ONLY in JSON with keys: verdict, explanation. Verdict must be GROUNDED, CONTRADICTED, or UNCERTAIN."
    
    res = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "temperature": 0}
    )
    ai_text = res.json()["choices"][0]["message"]["content"]
    return json.loads(ai_text)

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TruthGuard AI v2.0 - by Musa Zailani</title>
        <style>
            body {font-family: Arial; background: #0f172a; color: white; text-align: center; padding: 40px 20px;}
            h1 {font-size: 48px; color: #38bdf8; margin: 0;}
          .subtitle {font-size: 20px; margin: 10px 0 30px;}
          .btn {background: #38bdf8; color: #0f172a; padding: 14px 28px; text-decoration: none; border-radius: 10px; font-weight: bold;}
          .tag {background: #1e293b; padding: 8px 16px; border-radius: 20px; display: inline-block; margin: 5px;}
        </style>
    </head>
    <body>
        <h1>TruthGuard AI v2.0</h1>
        <p class="subtitle">The Default Data Cleaner for AI Companies</p>
        <div>
            <span class="tag">Batch Fact-Check</span>
            <span class="tag">Hallucination Detection</span>
            <span class="tag">Data Cleaning</span>
        </div>
        <br>
        <a href="/docs" class="btn">API Docs →</a>
        <p style="margin-top:30px;"><a href="/stats" style="color:#38bdf8;">View Stats</a></p>
    </body>
    </html>
    """

@app.post("/fact-check")
async def fact_check(request: ClaimRequest, req: Request):
    log_visit(req.client.host, request.claim, "single")
    result = await fact_check_single(request.claim)
    return result

@app.post("/clean-dataset")
async def clean_dataset(request: BatchRequest, req: Request):
    """
    THE MONEY MAKER: Clean 1000s of claims at once
    Input: ["claim 1", "claim 2", "claim 3"]
    Output: Only GROUNDED claims + report
    """
    log_visit(req.client.host, f"{len(request.claims)} claims", "batch")
    
    results = []
    grounded_claims = []
    contradicted = 0
    uncertain = 0
    
    # Process all claims
    for claim in request.claims:
        result = await fact_check_single(claim)
        results.append({"claim": claim, "verdict": result["verdict"], "explanation": result["explanation"]})
        
        if result["verdict"] == "GROUNDED":
            grounded_claims.append(claim)
        elif result["verdict"] == "CONTRADICTED":
            contradicted += 1
        else:
            uncertain += 1
    
    return {
        "total_processed": len(request.claims),
        "grounded_count": len(grounded_claims),
        "contradicted_count": contradicted,
        "uncertain_count": uncertain,
        "clean_dataset": grounded_claims, # This is what AI companies will train on
        "full_report": results
    }

@app.get("/stats")
def stats():
    try:
        with open(VISITOR_LOG, "r") as f:
            logs = json.load(f)
        return {"total_visits": len(logs), "visits": logs[-50:]} # last 50
    except:
        return {"total_visits": 0, "visits": []}

@app.get("/health")
def health():
    return {"status": "LIVE v2.0", "founder": "Musa Zailani"}