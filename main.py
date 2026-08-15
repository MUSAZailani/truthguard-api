from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import httpx
import hmac
import hashlib

app = FastAPI()

# CORS - allow your frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
FRONTEND_URL = "https://truthguard-api-production-d58a.up.railway.app"

@app.get("/")
def home():
    return {"message": "TruthGuard API is live"}

@app.post("/initialize-payment")
async def initialize_payment(request: Request):
    data = await request.json()
    email = data.get("email")
    amount = int(data.get("amount")) * 100 # Paystack uses kobo
    
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "email": email,
        "amount": amount,
        "callback_url": f"{FRONTEND_URL}/verify" # This is where user lands after payment
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
        # TODO: Add credits to user here in DB
        return RedirectResponse(url=f"{FRONTEND_URL}?status=success")
    else:
        return RedirectResponse(url=f"{FRONTEND_URL}?status=failed")

@app.post("/webhook")
async def paystack_webhook(request: Request):
    # This is what Paystack calls to confirm payment
    payload = await request.body()
    sig = request.headers.get("x-paystack-signature")
    secret = PAYSTACK_SECRET_KEY.encode()
    hash = hmac.new(secret, payload, hashlib.sha512).hexdigest()
    
    if hash != sig:
        return JSONResponse(status_code=400, content={"status": "Invalid signature"})
    
    event = await request.json()
    if event["event"] == "charge.success":
        # TODO: Add credits to user here. This is the safest way
        email = event["data"]["customer"]["email"]
        amount = event["data"]["amount"] / 100
        print(f"Payment success for {email} - ₦{amount}")
        
    return {"status": "success"}