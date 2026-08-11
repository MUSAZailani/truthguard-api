from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io, csv, requests, os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CREDITS = 1000
GROQ_API_KEY = os.getenv("GROQ_API_KEY") # READS FROM RAILWAY VARIABLES

def clean_with_ai(text):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    prompt = f"You are TruthGuard AI. Clean this business data row and give a verdict: True, False, or Partially True. Explain why in 1 sentence. Data: {text}"
    r = requests.post("https://api.groq.com/openai/v1/chat/completions", 
        headers=headers, 
        json={"model":"llama3-8b-8192","messages":[{"role":"user","content":prompt}]})
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
        if CREDITS <= 0: 
            break
        original = ",".join(row)
        ai_result = clean_with_ai(original)
        results.append({
            "original": original, 
            "cleaned": ai_result, 
            "verdict": "AI Checked", 
            "explanation": "Processed by TruthGuard"
        })
        CREDITS -= 1
    
    return {"results": results, "credits_left": CREDITS}

@app.get("/download/pdf")
def download_pdf():
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, "TruthGuard Audit Report")
    p.setFont("Helvetica", 12)
    p.drawString(100, 730, f"Credits Left: {CREDITS}")
    p.drawString(100, 710, "All data processed by AI")
    p.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment;filename=TruthGuard_Report.pdf"})

@app.get("/download/csv")
def download_csv():
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Credits Left", CREDITS])
    writer.writerow(["Status", "Processing Complete"])
    buffer.seek(0)
    return StreamingResponse(io.BytesIO(buffer.getvalue().encode()), 
        media_type="text/csv", headers={"Content-Disposition": "attachment;filename=TruthGuard_Cleaned.csv"})