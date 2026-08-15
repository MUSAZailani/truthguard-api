from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import httpx

app = FastAPI()

# Allow frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
FRONTEND_URL = "https://truthguard-api-production-d58a.up.railway.app"

# SERVE YOUR FRONTEND
@app.get("/")
def home():
    return FileResponse("index.html")

# YOUR AI ENDPOINT - THIS IS TRUTHGUARD
@app.post("/analyze")
async def analyze_text(request: Request):
    data = await request.json()
    text = data.get("text")
    
    # PUT YOUR AI LOGIC HERE
    # Example:
    result = {
        "verdict": "Likely Real",
        "confidence": 92,
        "explanation": f"Analyzed: {text[:50]}..."
    }
    return JSONResponse(result)

# PAYSTACK PAYMENT
@app.post("/initialize-payment")
async def initialize_payment(request: Request):
    data = await request.json()
    email = data.get("email")
    amount = int(data.get("amount")) * 100 # kobo
    
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    payload = {
        "email": email,
        "amount": amount,
        "callback_url": f"{FRONTEND_URL}/verify"
    }
    
    async with httpx.AsyncClient() as client:
        res = await client.post("https://api.paystack.co/transaction/initialize", json=payload, headers=headers)
        return res.json()

@app.get("/verify")
async def verify_payment(reference: str):
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)
        data = res.json()
        
    if data["data"]["status"] == "success":
        return RedirectResponse(url=f"{FRONTEND_URL}?status=success")
    else:
        return RedirectResponse(url=f"{FRONTEND_URL}?status=failed")