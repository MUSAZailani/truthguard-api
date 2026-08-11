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
    <!DOCTYPE html><html><head><title>TruthGuard AI</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
    body{font-family:Arial;background:#0f172a;color:white;text-align:center;padding:20px}
    h1{font-size:36px;color:#38bdf8} 
   .box{background:#1e293b;padding:30px;border-radius:12px;max-width:500px;margin:40px auto}
    input[type=file]{margin:20px 0;color:white}
    button{background:#38bdf8;color:#0f172a;padding:14px 28px;border:none;border-radius:10px;font-weight:bold;font-size:16px;cursor:pointer}
    button:hover{background:#0ea5e9}
   .note{font-size:12px;color:#94a3b8;margin-top:15px}
    </style></head><body>
    <h1>TruthGuard AI v2.3</h1>
    <p>Upload your CSV → Download Clean CSV</p>
    <div class="box">
      <form action="/upload-csv" method="post" enctype="multipart/form-data">
        <p>CSV must have a column named: <b>claim</b></p>
        <input type="file" name="file" accept=".csv" required><br>
        <button type="submit">Clean My Data</button>
      </form>
      <p class="note">Example: claim\\nNigeria is in Africa\\nThe moon is cheese</p>
    </div>
    <a href="/docs" style="color:#38bdf8">API Docs</a>
    </body></html>"""

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
async def upload_csv(req: Request, file: UploadFile = File(...)):
    log_visit(req.client.host, f"CSV: {file.filename}", "csv_upload")
    contents = await file.read()
    csv_reader = csv.DictReader(io.StringIO(contents.decode('utf-8')))
    claims = [row['claim'] for row in csv_reader]
    batch_size = 30
    clean_rows = []
    for i in range(0, len(claims), batch_size):
        batch = claims[i:i+batch_size]
        result = await clean_dataset(BatchRequest(claims=batch), req)
        for item in result["full_report"]:
            if item["verdict"] == "GROUNDED":
                clean_rows.append({"claim": item["claim"], "verdict": item["verdict"]})
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["claim", "verdict"])
    writer.writeheader()
    writer.writerows(clean_rows)
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=clean_data.csv"})