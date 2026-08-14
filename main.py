import os
import csv
import io
import uuid
import asyncio
import httpx
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from groq import Groq

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ========== CONFIG - ADD YOUR KEYS HERE ==========
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY") # You just added this
MODEL = "openai/gpt-oss-20b" # NEW MODEL

CREDITS_PER_50_ROWS = 1
FREE_CREDITS_NEW_USER = 500

DB = {} # Temporary storage. Later use database
client = Groq(api_key=GROQ_API_KEY)

# ========== UTILS ==========
def get_user(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        user_id = str(uuid.uuid4())
    if user_id not in DB:
        DB[user_id] = {"credits": FREE_CREDITS_NEW_USER} # 500 FREE FOR NEW
    return user_id, DB[user_id]

async def clean_chunk(chunk):
    prompt = f"Clean and fact-check these rows. Return JSON array with keys: original, cleaned, verdict, explanation. Data: {chunk}"
    res = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=MODEL,
        response_format={"type": "json_object"},
    )
    return res.choices[0].message.content

# ========== 3 PAGES ==========
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

@app.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    user_id, user = get_user(request)
    return templates.TemplateResponse("pricing.html", {"request": request, "credits": user["credits"]})

# ========== CLEAN DATA ONLY BUTTON ==========
@app.post("/clean")
async def process_clean(request: Request, file: UploadFile = File(None), text_data: str = Form("")):
    user_id, user = get_user(request)

    if user["credits"] <= 0:
        return templates.TemplateResponse("clean.html", {"request": request, "credits": 0, "error": "Kindly buy credits to continue"})

    # Read file
    data = []
    if file:
        content = await file.read()
        data = [row for row in content.decode("utf-8").split("\n") if row]
    elif text_data:
        data = [row for row in text_data.split("\n") if row]

    total_rows = len(data)
    credits_needed = (total_rows + 49) // 50 # 50 rows = 1 credit. Handles up to 5000

    if credits_needed > user["credits"]:
        return templates.TemplateResponse("clean.html", {"request": request, "credits": user["credits"], "error": f"Not enough credits. Need {credits_needed}. Kindly buy credits to continue"})

    user["credits"] -= credits_needed

    # Process fast in chunks
    chunks = [data[i:i + 50] for i in range(0, min(total_rows, 5000), 50)]
    results = await asyncio.gather(*[clean_chunk(c) for c in chunks])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["original", "cleaned", "verdict", "explanation"])
    # parse results here...
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment;filename=cleaned.csv"})

# ========== 4 PAYMENT METHODS ==========
@app.post("/pay")
async def pay(request: Request, plan: str = Form(...)):
    plans = {"500": 7000, "1000": 50000, "10000": 75000, "20000": 150000}
    amount = plans.get(plan, 7000)
    user_id, _ = get_user(request)

    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    data = {
        "amount": amount * 100,
        "metadata": {"user_id": user_id, "credits": plan},
        "channels": ["card", "bank_transfer", "bank", "ussd"] # 4 METHODS
    }
    async with httpx.AsyncClient() as http:
        res = await http.post("https://api.paystack.co/transaction/initialize", json=data, headers=headers)

    return RedirectResponse(res.json()["data"]["authorization_url"], status_code=303)