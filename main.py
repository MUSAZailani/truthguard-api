from fastapi import FastAPI, Depends, HTTPException, Header, Request
from pydantic import BaseModel
import sqlite3
import time
import stripe
import os

app = FastAPI(title="TruthGuard API")

# STRIPE SETUP
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# 1. DATABASE SETUP
conn = sqlite3.connect('truthguard.db', check_same_thread=False)
conn.execute('''CREATE TABLE IF NOT EXISTS api_keys
                (key TEXT PRIMARY KEY, email TEXT, plan TEXT, claims_used INT DEFAULT 0, created_at REAL)''')
conn.execute('''CREATE TABLE IF NOT EXISTS usage_log
                (id INTEGER PRIMARY KEY, api_key TEXT, claim TEXT, verdict TEXT, timestamp REAL)''')
conn.commit()

# 2. DEMO KEYS
DEMO_KEYS = {
    "tg_free_001": {"limit": 1000, "plan": "free"},
    "tg_dev_002": {"limit": 10000, "plan": "developer"},
    "tg_growth_003": {"limit": 250000, "plan": "growth"}
}

for k, v in DEMO_KEYS.items():
    conn.execute("INSERT OR IGNORE INTO api_keys (key, plan, claims_used, created_at) VALUES (?,?, 0,?)",
                 (k, v["plan"], time.time()))
conn.commit()

# 3. AUTH FUNCTION
def verify_api_key(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header. Use: Bearer YOUR_API_KEY")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid format. Use: Bearer YOUR_API_KEY")
    api_key = authorization.replace("Bearer ", "")
    if api_key not in DEMO_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    cur = conn.execute("SELECT claims_used FROM api_keys WHERE key=?", (api_key,))
    row = cur.fetchone()
    claims_used = row[0] if row else 0
    if claims_used >= DEMO_KEYS[api_key]["limit"]:
        raise HTTPException(status_code=429, detail=f"Monthly limit of {DEMO_KEYS[api_key]['limit']} reached.")
    return api_key

# 4. YOUR EXISTING TRUTHGUARD FUNCTION
def run_truthguard(claim: str):
    return {
        "claim": claim,
        "verdict": "GROUNDED",
        "confidence": 0.95,
        "explanation": "Checked against knowledge base",
        "sources": ["https://example.com"]
    }

# 5. PROTECTED ENDPOINT
class ClaimRequest(BaseModel):
    claim: str

@app.post("/fact-check")
def fact_check(request: ClaimRequest, api_key: str = Depends(verify_api_key)):
    result = run_truthguard(request.claim)
    conn.execute("INSERT INTO usage_log (api_key, claim, verdict, timestamp) VALUES (?,?,?,?)",
                 (api_key, request.claim, result["verdict"], time.time()))
    conn.execute("UPDATE api_keys SET claims_used = claims_used + 1 WHERE key=?", (api_key,))
    conn.commit()
    return {"result": result}

@app.get("/usage")
def get_usage(api_key: str = Depends(verify_api_key)):
    cur = conn.execute("SELECT claims_used FROM api_keys WHERE key=?", (api_key,))
    used = cur.fetchone()[0]
    limit = DEMO_KEYS[api_key]["limit"]
    return {"plan": DEMO_KEYS[api_key]["plan"], "claims_used": used, "claims_remaining": limit - used}

# 6. STRIPE CHECKOUT - FIXED
@app.get("/create-checkout")
@app.post("/create-checkout")
def create_checkout(plan: str, email: str):
    if not STRIPE_PRICE_ID:
        raise HTTPException(status_code=500, detail="STRIPE_PRICE_ID not set in Railway")

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price': STRIPE_PRICE_ID, # Use the Price ID from Stripe
            'quantity': 1,
        }],
        mode='payment',
        customer_email=email,
        success_url='https://google.com',
        cancel_url='https://google.com',
    )
    return {"url": checkout_session.url}

# 7. WEBHOOK
@app.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(status_code=400, detail="Webhook error")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session["customer_email"]
        print(f"PAID! Email: {customer_email}")
    return {"status": "success"}