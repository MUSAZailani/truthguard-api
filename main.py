import os
import requests
import json
import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(
    title="TruthGuard AI v2.1",
    description="The Default Data Cleaning Layer for AI Companies. Batch fact-check 1000s of claims with strict verification.",
    version="2.1.0",
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
    """SMART FACT CHECKER - Strict rules"""
    prompt = f"""You are an expert fact-checker and data cleaner for AI training.
STRICT RULES:
1. If the claim is scientifically, biologically, or historically FALSE, verdict MUST be CONTRADICTED.
2. If the claim is TRUE and verifiable with evidence, verdict is GROUNDED.
3. If you cannot verify with confidence, verdict is UNCERTAIN.
4. Examples: "Cats can fly" = CONTRADICTED. "The earth is flat" = CONTRADICTED.

Claim: '{claim}'. 
Respond ONLY in valid JSON with keys: verdict, explanation. 
Verdict must be exactly: GROUNDED, CONTRADICTED, or UNCERTAIN."""
    
    res = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": "llama-3.1-8b-instant", 
            "messages": [{"role": "user", "content": prompt}], 
            "temperature": 0,
            "max_tokens": 300
        }
    )
    ai_text = res.json()["choices"][0]["message"]["content"]
    
    # Clean JSON in case Groq adds markdown
    ai_text = ai_text.replace("```json", "").replace("```", "")
    return json.loads(ai_text.strip())

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TruthGuard AI v2.1 - by Musa Zailani</title>
        <style>
            body {font-family: Arial; background: #0f172a; color: white; text-align: center; padding: 40px 20px;}
            h1 {font-size: 48px; color: #38bdf8; margin: 0;}
           .subtitle {font-size: 20px; margin: 10px 0 30px;}
           .btn {background: #38bdf8; color: #0f172a; padding: 14px 28px; text-decoration: none; border-radius: 10px; font-weight: bold;}
           .tag {background: #1e293b; padding: 8px 16px; border-radius: 20px; display: inline-block; margin: 5px;}
        </style>
    </head>
    <body>
        <h1>TruthGuard AI v2.1</h1>
        <p class="subtitle">The Default Data Cleaner for AI Companies</p>
        <div>
            <span class="tag">Batch Fact-Check</span>
            <span class="tag">Hallucination Detection</span>
            <span class="tag">Strict Verification</span>
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
    THE MONEY MAKER: Clean 1000s of claims at once for AI training
    """
    log_visit(req.client.host, f"{len(request.claims)} claims", "batch")
    
    results = []
    grounded_claims = []
    contradicted = 0
    uncertain = 0
    
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
        "clean_dataset": grounded_claims,
        "full_report": results
    }

@app.get("/stats")
def stats():
    try:
        with open(VISITOR_LOG, "r") as f:
            logs = json.load(f)
        return {"total_visits": len(logs), "visits": logs[-50:]}
    except:
        return {"total_visits": 0, "visits": []}

@app.get("/health")
def health():
    return {"status": "LIVE v2.1", "founder": "Musa Zailani"}