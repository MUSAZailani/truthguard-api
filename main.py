from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io, csv, requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CREDITS = 1000
GROQ_API_KEY = "gsk_your_key_here" # PUT YOUR GROQ KEY HERE

def clean_with_ai(text):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    prompt = f"Clean this business claim and give verdict True/False/Partially True: {text}"
    r = requests.post("https://api.groq.com/openai/v1/chat/completions", 
        headers=headers, json={"model":"llama3-8b-8192","messages":[{"role":"user","content":prompt}]})
    return r.json()["choices"][0]["message"]["content"]

@app.get("/credits")
def get_credits():
    return {"credits": CREDITS}

@app.post("/clean")
async def clean_csv(file: UploadFile = File(...)):
    global CREDITS
    content = await file.read()
    rows = list(csv.reader(io.StringIO(content.decode('utf-8'))))
    results = []
    for row in rows[1:]: # skip header
        if CREDITS <= 0: break
        original = ",".join(row)
        cleaned = clean_with_ai(original)
        results.append({"original": original, "cleaned": cleaned, "verdict": "Checked", "explanation": "AI verified"})
        CREDITS -= 1
    return {"results": results}

@app.get("/download/pdf")
def download_pdf():
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.drawString(100, 750, "TruthGuard Audit Report")
    p.drawString(100, 730, f"Credits Left: {CREDITS}")
    p.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment;filename=report.pdf"})