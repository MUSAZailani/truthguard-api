import os
import requests
import json
import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(
    title="TruthGuard AI",
    description="AI-Powered Fact Checking API. Verify any claim instantly with Groq LLM.",
    version="1.5.0",
    contact={"name": "Musa Zailani", "email": "zailaniheman@gmail.com"}
)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
VISITOR_LOG = "visitors.json"

class ClaimRequest(BaseModel):
    claim: str

def log_visit(ip: str, claim: str):
    """Save visitor data to file"""
    log_entry = {
        "time": datetime.datetime.now().isoformat(),
        "ip": ip,
        "claim": claim
    }
    
    # Read existing logs
    try:
        with open(VISITOR_LOG, "r") as f:
            logs = json.load(f)
    except:
        logs = []
    
    # Add new log
    logs.append(log_entry)
    
    # Save back
    with open(VISITOR_LOG, "w") as f:
        json.dump(logs, f, indent=2)

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TruthGuard AI - by Musa Zailani</title>
        <style>
            body {font-family: Arial; background: #0f172a; color: white; text-align: center; padding: 60px 20px;}
            h1 {font-size: 52px; color: #38bdf8; margin: 0;}
          .subtitle {font-size: 22px; margin: 10px 0 30px;}
          .btn {background: #38bdf8; color: #0f172a; padding: 16px 32px; text-decoration: none; border-radius: 10px; font-weight: bold; font-size: 18px;}
        </style>
    </head>
    <body>
        <h1>TruthGuard AI</h1>
        <p class="subtitle">Fact Checking by <b>Musa Zailani</b></p>
        <a href="/docs" class="btn">Try it Free →</a>
        <p style="margin-top:30px;"><a href="/stats" style="color:#38bdf8;">View Stats</a></p>
    </body>
    </html>
    """

@app.post("/fact-check")
async def fact_check(request: ClaimRequest, req: Request):
    claim = request.claim
    client_ip = req.client.host
    
    # LOG THE VISIT
    log_visit(client_ip, claim)
    
    prompt = f"You are a fact-checker. Claim: '{claim}'. Respond ONLY in JSON with keys: verdict and explanation. Verdict must be GROUNDED, CONTRADICTED, or UNCERTAIN."
    
    res = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}]}
    )
    
    ai_text = res.json()["choices"][0]["message"]["content"]
    return json.loads(ai_text)

@app.get("/stats")
def stats():
    """View all visitors"""
    try:
        with open(VISITOR_LOG, "r") as f:
            logs = json.load(f)
        return {"total_visits": len(logs), "visits": logs}
    except:
        return {"total_visits": 0, "visits": []}

@app.get("/health")
def health():
    return {"status": "LIVE", "founder": "Musa Zailani"}