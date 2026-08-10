import os
import requests
import json
import datetime
import csv
import io
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

app = FastAPI(
    title="TruthGuard AI v2.2",
    description="Upload CSV → Get Clean CSV. The Data Cleaning Layer for AI Companies.",
    version="2.2.0",
    contact={"name": "Musa Zailani", "email": "zailaniheman@gmail.com"}
)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
VISITOR_LOG = "visitors.json"

class ClaimRequest(BaseModel):
    claim: str

class BatchRequest(BaseModel):
    claims: list[str]

def log_visit(ip: str, claim: str, endpoint: str):
    log_entry = {"time": datetime.datetime.now().isoformat(), "ip": ip, "endpoint": endpoint, "claim": claim}
    try:
        with open(VISITOR_LOG, "r") as f: logs = json.load(f)
    except: logs = []
    logs.append(log_entry)
    with open(VISITOR_LOG, "w") as f: json.dump(logs, f, indent=2)

async def fact_check_single(claim: str):
    prompt = f"""You are an expert fact-checker. 
STRICT RULES: If the claim is scientifically/biologically FALSE, verdict MUST be CONTRADICTED.
Claim: '{claim}'. Respond ONLY in valid JSON with keys: verdict, explanation. 
Verdict must be: GROUNDED, CONTRADICTED, or UNCERTAIN."""
    
    res = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "temperature": 0}
    )
    ai_text = res.json()["choices"][0]["message"]["content"]
    ai_text = ai_text.replace("```json", "").replace("```", "")
    return json.loads(ai_text.strip())

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html><html><head><title>TruthGuard AI v2.2</title>
    <style>body{font-family:Arial;background:#0f172a;color:white;text-align:center;padding:40px}
    h1{font-size:48px;color:#38bdf8}.btn{background:#38bdf8;color:#0f172a;padding:14px 28px;text-decoration:none;border-radius:10px;font-weight:bold}</style>
    </head><body><h1>TruthGuard AI v2.2</h1>
    <p>Upload CSV → Get Clean CSV</p><br>
    <a href="/docs" class="btn">Try CSV Upload →</a></body></html>"""

@app.post("/fact-check")
async def fact_check(request: ClaimRequest, req: Request):
    log_visit(req.client.host, request.claim, "single")
    return await fact_check_single(request.claim)

@app.post("/clean-dataset")
async def clean_dataset(request: BatchRequest, req: Request):
    log_visit(req.client.host, f"{len(request.claims)} claims", "batch")
    results = []; grounded_claims = []; contradicted = 0; uncertain = 0
    for claim in request.claims:
        result = await fact_check_single(claim)
        results.append({"claim": claim, "verdict": result["verdict"], "explanation": result["explanation"]})
        if result["verdict"] == "GROUNDED": grounded_claims.append(claim)
        elif result["verdict"] == "CONTRADICTED": contradicted += 1
        else: uncertain += 1
    return {"total_processed": len(request.claims), "grounded_count": len(grounded_claims), "contradicted_count": contradicted, "uncertain_count": uncertain, "clean_dataset": grounded_claims, "full_report": results}

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...), req: Request):
    """
    NEW: Upload a CSV with a 'claim' column. Get back a clean CSV with only GROUNDED claims.
    """
    log_visit(req.client.host, f"CSV: {file.filename}", "csv_upload")
    
    contents = await file.read()
    csv_reader = csv.DictReader(io.StringIO(contents.decode('utf-8')))
    
    claims = [row['claim'] for row in csv_reader] # Expects column named "claim"
    
    # Process in batches
    batch_size = 30
    clean_rows = []
    
    for i in range(0, len(claims), batch_size):
        batch = claims[i:i+batch_size]
        result = await clean_dataset(BatchRequest(claims=batch), req)
        for item in result["full_report"]:
            if item["verdict"] == "GROUNDED":
                clean_rows.append({"claim": item["claim"], "verdict": item["verdict"]})
    
    # Return new CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["claim", "verdict"])
    writer.writeheader()
    writer.writerows(clean_rows)
    
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=clean_data.csv"})

@app.get("/stats")
def stats():
    try:
        with open(VISITOR_LOG, "r") as f: logs = json.load(f)
        return {"total_visits": len(logs), "visits": logs[-50:]}
    except: return {"total_visits": 0, "visits": []}

@app.get("/health")
def health(): return {"status": "LIVE v2.2", "founder": "Musa Zailani"}