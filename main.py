from fastapi import FastAPI, Form, UploadFile, File, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer
import pandas as pd
import io
import uuid
import base64
import re
import json
import os
import requests
import psycopg2
import bcrypt # pip install bcrypt

app = FastAPI(title="TruthGuard AI")

NEW_USER_CREDITS = 500
PAYSTACK_LIVE_KEY = os.getenv("PAYSTACK_LIVE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
BASE_URL = "https://truthguard-api-production-d58a.up.railway.app"

PLANS = {
    "500": {"price": 7000, "credits": 500, "name": "Starter"},
    "1000": {"price": 50000, "credits": 1000, "name": "Pro"},
    "10000": {"price": 75000, "credits": 10000, "name": "Business"},
    "20000": {"price": 150000, "credits": 20000, "name": "Enterprise"}
}

# CREATE TABLE ONCE
def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id SERIAL PRIMARY KEY, 
                  email TEXT UNIQUE NOT NULL, 
                  password_hash TEXT NOT NULL,
                  credits INTEGER DEFAULT 500)''')
    conn.commit()
    conn.close()

init_db()

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode()

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def get_user(email):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, email, password_hash, credits FROM users WHERE email=%s", (email,))
    result = c.fetchone()
    conn.close()
    return result

def create_user(email, password):
    conn = get_db()
    c = conn.cursor()
    hashed = hash_password(password)
    c.execute("INSERT INTO users (email, password_hash, credits) VALUES (%s,%s,%s)", (email, hashed, NEW_USER_CREDITS))
    conn.commit()
    conn.close()

def get_credits(email):
    user = get_user(email)
    return user[3] if user else NEW_USER_CREDITS

def use_credits(email, amount):
    conn = get_db()
    c = conn.cursor()
    current = get_credits(email)
    if current >= amount:
        new_credits = current - amount
        c.execute("UPDATE users SET credits=%s WHERE email=%s", (new_credits, email))
        conn.commit()
    conn.close()
    return current >= amount

def add_credits(email, amount):
    conn = get_db()
    c = conn.cursor()
    current = get_credits(email)
    new_credits = current + amount
    c.execute("UPDATE users SET credits=%s WHERE email=%s", (new_credits, email))
    conn.commit()
    conn.close()

def get_current_user(request: Request):
    email = request.cookies.get("tg_email")
    if not email: return None
    return email

#... keep your SPELL_DICT, clean_text, smart_clean functions same...

def NAVBAR(email, credits):
    login_btn = f'<span style="color:#00ff88">{email}</span> <a href="/logout" style="color:#fff">Logout</a>' if email else '<a href="/login" style="color:#fff">Login</a> <a href="/signup" style="color:#fff">Sign Up</a>'
    return f"""<div style="background:#0d0d0d;padding:15px 20px;border-bottom:2px solid #00ff88;position:sticky;top:0;z-index:100">
<div style="max-width:900px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap">
<div style="display:flex;align-items:center;gap:10px"><span style="font-size:2em">🛡️</span><b style="font-size:1.3em;color:#00ff88">TruthGuard AI</b></div>
<div style="display:flex;gap:25px;align-items:center;flex-wrap:wrap">
<a href="/" style="color:#fff;text-decoration:none;font-weight:bold">Home</a>
<a href="/clean" style="color:#fff;text-decoration:none;font-weight:bold">Cleaning</a>
<a href="/pricing" style="color:#fff;text-decoration:none;font-weight:bold">Pricing</a>
<div style="background:#1a1a1a;padding:8px 18px;border-radius:25px;border:1px solid #333">Credits: {credits}</div>
{login_btn}
</div></div></div>"""

CSS = """<style>body{background:#0a0a0a;color:#e0e0e0;font-family:Arial, sans-serif;margin:0;padding:0}.container{max-width:1000px;margin:0 auto;padding:30px 20px}.btn{background:#00ff88;color:#000;padding:16px 25px;border-radius:10px;text-decoration:none;font-weight:bold;display:inline-block;font-size:1em;border:none;cursor:pointer;width:100%;margin:8px 0}.btn:hover{background:#00dd77}.btn-secondary{background:#1a1a1a;color:#fff;border:1px solid #333}input,textarea{width:100%;padding:14px;margin:12px 0;border-radius:10px;border:1px solid #333;background:#111;color:#fff;box-sizing:border-box;font-size:1em}.error{color:#ff4444;font-weight:bold;text-align:center;padding:12px;background:#1a0000;border:1px solid #ff4444;border-radius:8px;margin:15px 0}.success{color:#00ff88;font-weight:bold;text-align:center;padding:12px;background:#001a00;border:1px solid #00ff88;border-radius:8px;margin:15px 0}.download{background:#00ff88;color:#000;padding:14px;text-align:center;border-radius:10px;text-decoration:none;display:block;font-weight:bold;margin:15px 0}.card{background:#111;padding:30px;border-radius:15px;border:2px solid #333;text-align:center}.grid{display:grid;grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));gap:20px;margin-top:20px}.price{font-size:2.5em;font-weight:bold;color:#00ff88;margin:10px 0}</style>"""

def LOGIN_PAGE(message=""):
    return f"<!DOCTYPE html><html><head><title>Login - TruthGuard AI</title><meta name=viewport content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{NAVBAR(None,500)}<div class=container style=max-width:400px><h1 style=text-align:center;color:#00ff88>Login</h1><p class=error>{message}</p><form method=post><input name=email type=email placeholder=Email required><input name=password type=password placeholder=Password required><button type=submit class=btn>Login</button></form><p style=text-align:center>Don't have account? <a href=/signup style=color:#00ff88>Sign Up</a></p></div></body></html>"

def SIGNUP_PAGE(message=""):
    return f"<!DOCTYPE html><html><head><title>Sign Up - TruthGuard AI</title><meta name=viewport content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{NAVBAR(None,500)}<div class=container style=max-width:400px><h1 style=text-align:center;color:#00ff88>Sign Up</h1><p class=error>{message}</p><form method=post><input name=email type=email placeholder=Email required><input name=password type=password placeholder=Password required><button type=submit class=btn>Create Account - {NEW_USER_CREDITS} Free Credits</button></form><p style=text-align:center>Already have account? <a href=/login style=color:#00ff88>Login</a></p></div></body></html>"

# Update all your page functions to accept email instead of credits only
def HOME_PAGE(email, credits): return f"<!DOCTYPE html><html><head><title>TruthGuard AI</title><meta name=viewport content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{NAVBAR(email, credits)}<div class=container style=text-align:center><div style=font-size:5em;margin:20px 0>🛡️</div><h1 style=color:#00ff88>TruthGuard AI</h1><p style=color:#aaa;font-size:1.2em>AI Powered CSV & Text Cleaning</p><p style=color:#00ff88>Handles 5000+ rows instantly • 1 Credit = 1 Row</p><p style=color:#00ff88;font-size:1.1em>New Users Get {NEW_USER_CREDITS} Free Credits</p><div style=margin-top:40px><a href=/clean class=btn>CLEAN DATA</a></div></div></body></html>"

#... update CLEAN_PAGE, PRICING_PAGE, CHECKOUT_PAGE same way to accept email...

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    email = get_current_user(request)
    credits = get_credits(email) if email else NEW_USER_CREDITS
    response = HTMLResponse(HOME_PAGE(email, credits))
    return response

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return HTMLResponse(LOGIN_PAGE())

@app.post("/login", response_class=HTMLResponse)
async def login(email: str = Form(...), password: str = Form(...)):
    user = get_user(email)
    if not user or not verify_password(password, user[2]):
        return HTMLResponse(LOGIN_PAGE("Invalid email or password"))
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("tg_email", email)
    return response

@app.get("/signup", response_class=HTMLResponse)
async def signup_page():
    return HTMLResponse(SIGNUP_PAGE())

@app.post("/signup", response_class=HTMLResponse)
async def signup(email: str = Form(...), password: str = Form(...)):
    if get_user(email):
        return HTMLResponse(SIGNUP_PAGE("Email already exists"))
    create_user(email, password)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("tg_email", email)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse("/")
    response.delete_cookie("tg_email")
    return response

# UPDATE /clean to use email instead of session_id
@app.get("/clean", response_class=HTMLResponse)
async def clean_page(request: Request):
    email = get_current_user(request)
    if not email: return RedirectResponse("/login")
    credits = get_credits(email)
    disabled = "disabled" if credits <= 0 else ""
    message = "kindly buy credits to continue" if credits <= 0 else ""
    response = HTMLResponse(CLEAN_PAGE(email, credits, message, "error" if credits <= 0 else "", "", disabled))
    return response

@app.post("/clean", response_class=HTMLResponse)
async def clean_data(request: Request, file: UploadFile = File(None), text_data: str = Form(None)):
    email = get_current_user(request)
    if not email: return RedirectResponse("/login")
    credits = get_credits(email)
    if credits <= 0: return HTMLResponse(CLEAN_PAGE(email, 0, "kindly buy credits to continue", "error", "", "disabled"))
    #... rest of your cleaning logic but replace session_id with email...
    if credits < rows: return HTMLResponse(CLEAN_PAGE(email, credits, f"Not enough credits. This will cost {rows} credits. You have {credits}.", "error", "", ""))
    df_cleaned = smart_clean(df)
    use_credits(email, rows)
    new_credits = get_credits(email)
    #... rest same...
    message = f"✅ Cleaned {rows} rows! {rows} Credits Used. You have {new_credits} left."
    return HTMLResponse(CLEAN_PAGE(email, new_credits, message, "success", download_link, ""))

# UPDATE /pay and /verify to use email
@app.post("/pay")
async def pay(request: Request, plan: str = Form(...), method: str = Form(...)):
    email = get_current_user(request)
    if not email: return RedirectResponse("/login")
    plan_data = PLANS[plan]
    amount = plan_data["price"] * 100
    headers = {"Authorization": f"Bearer {PAYSTACK_LIVE_KEY}", "Content-Type": "application/json"}
    data = {"amount": amount, "email": email, "currency": "NGN", "channels": [method], "callback_url": f"{BASE_URL}/verify", "metadata": {"email": email, "credits": plan_data["credits"]}}
    res = requests.post("https://api.paystack.co/transaction/initialize", headers=headers, json=data)
    response_data = res.json()
    if response_data["status"]:
        return RedirectResponse(url=response_data["data"]["authorization_url"], status_code=303)
    else:
        return RedirectResponse(url="/pricing", status_code=303)

@app.get("/verify")
async def verify(request: Request, reference: str):
    headers = {"Authorization": f"Bearer {PAYSTACK_LIVE_KEY}"}
    res = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)
    data = res.json()
    if data["status"] and data["data"]["status"] == "success":
        metadata = data["data"]["metadata"]
        email = metadata["email"]
        credits = int(metadata["credits"])
        add_credits(email, credits)
    return RedirectResponse(url="/pricing?status=success", status_code=303)