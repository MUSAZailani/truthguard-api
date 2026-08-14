import os
import csv
import io
import uuid
import asyncio
import httpx
from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from groq import Groq

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ========== CONFIG ==========
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY") # PUT YOUR sk_live_ HERE
MODEL = "openai/gpt-oss-20b" # NEW MODEL
CREDITS_PER_ROW = 1
ROWS_PER_CREDIT = 50

# Fake DB for now. Later use Postgres
DB = {}

client = Groq(api_key=GROQ_API_KEY)

# ========== UTILS ==========
def get_user(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        user_id = str(uuid.uuid4())
    if user_id not in DB:
        DB[user_id] = {"credits": 500, "is_new": True} # 500 FREE FOR NEW
    return user_id, DB[user_id]

async def clean_and_fact_check_chunk(chunk):
    prompt = f"""
    You are TruthGuard AI. For each row below, do 2 things:
    1. Clean: Fix grammar, typos, standardize.
    2. Fact-Check: Return verdict True, False, Partially True. Add 1-line explanation.

    Return ONLY a JSON array of objects with keys: original, cleaned, verdict, explanation.

    Data: {chunk}
    """
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=MODEL,
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return chat_completion.choices[0].message.content

# ========== ROUTES ==========
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user_id, user = get_user(request)
    response = templates.TemplateResponse("home.html", {"request": request, "credits": user["credits"]})
    response.set_cookie(key="user_id", value=user_id)
    return response

@app.get("/clean", response_class=HTMLResponse)
async def clean_page(request: Request):
    user_id, user = get_user(request)
    return templates.TemplateResponse("clean.html", {"request": request, "credits": user["credits"]})

@app.post("/clean", response_class=HTMLResponse)
async def process_clean(request: Request, file: UploadFile = File(None), text_data: str = Form("")):
    user_id, user = get_user(request)

    if user["credits"] <= 0:
        return templates.TemplateResponse("clean.html", {"request": request, "credits": 0, "error": "Kindly buy credits to continue"})

    # Read data
    data = []
    if file:
        content = await file.read()
        decoded = content.decode("utf-8")
        reader = csv.reader(io.StringIO(decoded))
        data = [row[0] for row in reader]
    elif text_data:
        data = text_data.split("\n")

    total_rows = len(data)
    credits_needed = (total_rows + ROWS_PER_CREDIT - 1) // ROWS_PER_CREDIT

    if credits_needed > user["credits"]:
        return templates.TemplateResponse("clean.html", {"request": request, "credits": user["credits"], "error": f"Not enough credits. You need {credits_needed}, you have {user['credits']}. Kindly buy credits to continue"})

    # Deduct credits
    user["credits"] -= credits_needed
    user["is_new"] = False

    # Process in chunks of 50, up to 5000
    chunks = [data[i:i + 50] for i in range(0, min(total_rows, 5000), 50)]
    tasks = [clean_and_fact_check_chunk(chunk) for chunk in chunks]
    results = await asyncio.gather(*tasks)

    # Combine and return CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["original", "cleaned", "verdict", "explanation"])
    #... parse results and write...

    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment;filename=cleaned_data.csv"})

@app.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    user_id, user = get_user(request)
    return templates.TemplateResponse("pricing.html", {"request": request, "credits": user["credits"]})

@app.post("/pay")
async def pay(request: Request, plan: str = Form(...)):
    plans = {"500": 7000, "1000": 50000, "10000": 75000, "20000": 150000}
    amount = plans.get(plan, 7000)
    user_id, _ = get_user(request)

    # Initialize Paystack with 4 channels
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    data = {
        "email": "customer@email.com",
        "amount": amount * 100,
        "metadata": {"user_id": user_id, "credits": plan},
        "channels": ["card", "bank_transfer", "bank", "ussd"] # 4 METHODS
    }
    async with httpx.AsyncClient() as client_http:
        res = await client_http.post("https://api.paystack.co/transaction/initialize", json=data, headers=headers)
    return RedirectResponse(res.json()["data"]["authorization_url"], status_code=303)