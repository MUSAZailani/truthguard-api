import os, csv, io, uuid, asyncio, httpx
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from groq import Groq

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ========== KEYS FROM RAILWAY ==========
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
MODEL = "openai/gpt-oss-20b" # NEW SMART MODEL

DB = {}
client = Groq(api_key=GROQ_API_KEY)

def get_user(request: Request):
    user_id = request.cookies.get("user_id") or str(uuid.uuid4())
    if user_id not in DB:
        DB[user_id] = {"credits": 500} # 500 FREE FOR NEW CUSTOMERS
    return user_id, DB[user_id]

# ========== 3 PAGES ==========
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user_id, user = get_user(request)
    res = templates.TemplateResponse("home.html", {"request": request, "credits": user["credits"]})
    res.set_cookie("user_id", user_id)
    return res

@app.get("/clean", response_class=HTMLResponse)
async def clean_page(request: Request):
    _, user = get_user(request)
    return templates.TemplateResponse("clean.html", {"request": request, "credits": user["credits"]})

@app.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    _, user = get_user(request)
    return templates.TemplateResponse("pricing.html", {"request": request, "credits": user["credits"]})

# ========== CLEAN DATA ONLY - HANDLES 5000 ROWS ==========
@app.post("/clean")
async def process_clean(request: Request, file: UploadFile = File(None), text_data: str = Form("")):
    _, user = get_user(request)
    if user["credits"] <= 0:
        return templates.TemplateResponse("clean.html", {"request": request, "credits": 0, "error": "Kindly buy credits to continue"}) # RED TEXT

    data = (await file.read()).decode("utf-8").split("\n") if file else text_data.split("\n")
    data = [d for d in data if d.strip()]

    credits_needed = (len(data) + 49) // 50
    if credits_needed > user["credits"]:
        return templates.TemplateResponse("clean.html", {"request": request, "credits": user["credits"], "error": "Kindly buy credits to continue"})

    user["credits"] -= credits_needed

    # Fast async processing for 5000 rows
    chunks = [data[i:i+50] for i in range(0, min(len(data), 5000), 50)]
    await asyncio.gather(*[client.chat.completions.create(
        model=MODEL, messages=[{"role":"user","content":f"Clean and fact-check: {c}"}],
        response_format={"type":"json_object"}) for c in chunks])

    output = io.StringIO(); csv.writer(output).writerow(["original","cleaned","verdict","explanation"])
    output.seek(0)
    return StreamingResponse(output, headers={"Content-Disposition":"attachment;filename=cleaned.csv"})

# ========== 4 PAYMENT METHODS ==========
@app.post("/pay")
async def pay(request: Request, plan: str = Form(...)):
    plans = {"500": 7000, "1000": 50000, "10000": 75000, "20000": 150000}
    user_id, _ = get_user(request)
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    data = {"amount": plans[plan]*100, "metadata":{"user_id":user_id,"credits":plan}, "channels":["card","bank_transfer","bank","ussd"]}
    async with httpx.AsyncClient() as http:
        res = await http.post("https://api.paystack.co/transaction/initialize", json=data, headers=headers)
    return RedirectResponse(res.json()["data"]["authorization_url"], 303)