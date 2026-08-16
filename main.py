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

app = FastAPI(title="zailani")

NEW_USER_CREDITS = 500
PAYSTACK_LIVE_KEY = os.getenv("PAYSTACK_LIVE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
BASE_URL = "https://truthguard-api-production-d58a.up.railway.app" # change this to your zailani url later
ADMIN_KEY = "zailani_admin_2026" # CHANGED

PLANS = {
    "500": {"price": 7000, "credits": 500, "name": "Starter"},
    "1000": {"price": 50000, "credits": 1000, "name": "Pro"},
    "10000": {"price": 75000, "credits": 10000, "name": "Business"},
    "20000": {"price": 150000, "credits": 20000, "name": "Enterprise"}
}

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
    c.execute('''CREATE TABLE IF NOT EXISTS activity_log
                 (id SERIAL PRIMARY KEY,
                  email TEXT NOT NULL,
                  action TEXT NOT NULL,
                  rows INTEGER,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

def log_activity(email, action, rows=0):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO activity_log (email, action, rows) VALUES (%s,%s,%s)", (email, action, rows))
    conn.commit()
    conn.close()

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
    log_activity(email, "Account Created", 0)
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
    email = request.cookies.get("z_email") # CHANGED COOKIE NAME
    if not email: return None
    return email

SPELL_DICT = {
    'teh': 'the', 'adn': 'and', 'recieve': 'receive', 'seperate': 'separate',
    'definately': 'definitely', 'occured': 'occurred', 'goverment': 'government',
    'califonia': 'california', 'newyork': 'new york'
}

def clean_money(s):
    s = str(s).strip()
    match = re.match(r'\$?([\d\.]+)([KMB])', s, re.I)
    if match:
        num, unit = match.groups()
        num = float(num)
        if unit.upper() == 'K': num *= 1000
        elif unit.upper() == 'M': num *= 1000000
        elif unit.upper() == 'B': num *= 1000000000
        return str(int(num))
    return s

def clean_email(s):
    s = str(s).strip().lower()
    if re.match(r"[^@]+@[^@]+\.[^@]+", s):
        return s
    return ""

def clean_text(s):
    s = str(s).strip()
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'[^a-zA-Z0-9\s@._-]', '', s)
    words = s.split()
    words = [SPELL_DICT.get(w.lower(), w) for w in words]
    return ' '.join(words).title()

def smart_clean(df):
    df = df.drop_duplicates()
    df = df.fillna('')
    for col in df.columns:
        col_lower = col.lower()
        if 'email' in col_lower:
            df[col] = df[col].astype(str).apply(clean_email)
        elif 'fund' in col_lower or 'price' in col_lower or 'amount' in col_lower:
            df[col] = df[col].astype(str).apply(clean_money)
        else:
            df[col] = df[col].astype(str).apply(clean_text)
    return df

def NAVBAR(email, credits):
    login_btn = f'<span style="color:#00ff88">{email}</span> <a href="/logout" style="color:#fff">Logout</a>' if email else '<a href="/login" style="color:#fff">Login</a> <a href="/signup" style="color:#fff">Sign Up</a>'
    return f"""<div style="background:#0d0d0d;padding:15px 20px;border-bottom:2px solid #00ff88;position:sticky;top:0;z-index:100">
<div style="max-width:900px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap">
<div style="display:flex;align-items:center;gap:10px"><span style="font-size:2em">🧹</span><b style="font-size:1.3em;color:#00ff88">zailani</b></div>
<div style="display:flex;gap:25px;align-items:center;flex-wrap:wrap">
<a href="/" style="color:#fff;text-decoration:none;font-weight:bold">Home</a>
<a href="/clean" style="color:#fff;text-decoration:none;font-weight:bold">Cleaning</a>
<a href="/pricing" style="color:#fff;text-decoration:none;font-weight:bold">Pricing</a>
<div style="background:#1a1a1a;padding:8px 18px;border-radius:25px;border:1px solid #333">Credits: {credits}</div>
{login_btn}
</div></div></div>"""

CSS = """<style>body{background:#0a0a0a;color:#e0e0e0;font-family:Arial, sans-serif;margin:0;padding:0}.container{max-width:1000px;margin:0 auto;padding:30px 20px}.btn{background:#00ff88;color:#000;padding:16px 25px;border-radius:10px;text-decoration:none;font-weight:bold;display:inline-block;font-size:1em;border:none;cursor:pointer;width:100%;margin:8px 0}.btn:hover{background:#00dd77}.btn-secondary{background:#1a1a1a;color:#fff;border:1px solid #333}input,textarea{width:100%;padding:14px;margin:12px 0;border-radius:10px;border:1px solid #333;background:#111;color:#fff;box-sizing:border-box;font-size:1em}.error{color:#ff4444;font-weight:bold;text-align:center;padding:12px;background:#1a0000;border:1px solid #ff4444;border-radius:8px;margin:15px 0}.success{color:#00ff88;font-weight:bold;text-align:center;padding:12px;background:#001a00;border:1px solid #00ff88;border-radius:8px;margin:15px 0}.download{background:#00ff88;color:#000;padding:14px;text-align:center;border-radius:10px;text-decoration:none;display:block;font-weight:bold;margin:15px 0}.card{background:#111;padding:30px;border-radius:15px;border:2px solid #333;text-align:center}.grid{display:grid;grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));gap:20px;margin-top:20px}.price{font-size:2.5em;font-weight:bold;color:#00ff88;margin:10px 0}</style>"""

def LOGIN_PAGE(message=""):
    return f"<!DOCTYPE html><html><head><title>Login - zailani</title><meta name=viewport content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{NAVBAR(None,500)}<div class=container style=max-width:400px><h1 style=text-align:center;color:#00ff88>Login</h1><p class=error>{message}</p><form method=post><input name=email type=email placeholder=Email required><input name=password type=password placeholder=Password required><button type=submit class=btn>Login</button></form><p style=text-align:center>Don't have account? <a href=/signup style=color:#00ff88>Sign Up</a></p></div></body></html>"

def SIGNUP_PAGE(message=""):
    return f"<!DOCTYPE html><html><head><title>Sign Up - zailani</title><meta name=viewport content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{NAVBAR(None,500)}<div class=container style=max-width:400px><h1 style=text-align:center;color:#00ff88>Sign Up</h1><p class=error>{message}</p><form method=post><input name=email type=email placeholder=Email required><input name=password type=password placeholder=Password required><button type=submit class=btn>Create Account - {NEW_USER_CREDITS} Free Credits</button></form><p style=text-align:center>Already have account? <a href=/login style=color:#00ff88>Login</a></p></div></body></html>"

def HOME_PAGE(email, credits):
    return f"<!DOCTYPE html><html><head><title>zailani</title><meta name=viewport content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{NAVBAR(email, credits)}<div class=container style=text-align:center><div style=font-size:5em;margin:20px 0>🧹</div><h1 style=color:#00ff88>zailani</h1><p style=color:#aaa;font-size:1.2em>AI Powered CSV & Text Cleaning</p><p style=color:#00ff88>Handles 5000+ rows instantly • 1 Credit = 1 Row</p><p style=color:#00ff88;font-size:1.1em>New Users Get {NEW_USER_CREDITS} Free Credits</p><div style=margin-top:40px><a href=/clean class=btn>CLEAN DATA</a></div></div></body></html>"

def CLEAN_PAGE(email, credits, message="", msg_class="", download_link="", disabled=""):
    return f"<!DOCTYPE html><html><head><title>Cleaning - zailani</title><meta name=viewport content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{NAVBAR(email, credits)}<div class=container><h1 style=text-align:center;color:#00ff88>Cleaning</h1><p class={msg_class}>{message}</p>{download_link}<form method=post enctype=multipart/form-data><label><b>Upload CSV/TXT File:</b></label><input type=file name=file accept=.csv,.txt {disabled}><label><b>Or Paste Data Here:</b></label><textarea name=text_data rows=12 placeholder='Paste up to 5000 rows...' {disabled}></textarea><button type=submit class=btn {disabled}>CLEAN DATA</button></form></div></body></html>"

def PRICING_PAGE(email, credits):
    cards = ""
    for key, plan in PLANS.items():
        cards += f"""<div class=card><h2>{plan['name']}</h2><div class=price>₦{plan['price']:,}</div><p>{plan['credits']:,} Credits</p><a href=/checkout/{key} class=btn>Buy Now</a></div>"""
    return f"<!DOCTYPE html><html><head><title>Pricing - zailani</title><meta name=viewport content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{NAVBAR(email, credits)}<div class=container><h1 style=text-align:center;color:#00ff88>Choose Your Plan</h1><p style=text-align:center;color:#aaa>Pay once. Use forever. 1 Credit = 1 Row Cleaned</p><div class=grid>{cards}</div></body></html>"

def CHECKOUT_PAGE(email, credits, plan_key):
    plan = PLANS[plan_key]
    return f"<!DOCTYPE html><html><head><title>Checkout - zailani</title><meta name=viewport content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{NAVBAR(email, credits)}<div class=container style=max-width:500px><h1 style=text-align:center;color:#00ff88>Complete Payment</h1><div class=card><h2>{plan['name']} Plan</h2><div class=price>₦{plan['price']:,}</div><p>{plan['credits']:,} Credits</p><hr style=border-color:#333;margin:20px 0><h3 style=text-align:center>Choose Payment Method</h3><form method=post action=/pay><input type=hidden name=plan value={plan_key}><button class=btn name=method value=card>Pay with Card</button><button class=btn btn-secondary name=method value=bank>Pay with Bank</button><button class=btn btn-secondary name=method value=ussd>Pay with USSD</button><button class=btn btn-secondary name=method value=qr>Pay with QR</button></form><br><a href=/pricing style=color:#00ff88>← Back to Plans</a></div></div></body></html>"

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    email = get_current_user(request)
    credits = get_credits(email) if email else NEW_USER_CREDITS
    return HTMLResponse(HOME_PAGE(email, credits))

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return HTMLResponse(LOGIN_PAGE())

@app.post("/login", response_class=HTMLResponse)
async def login(email: str = Form(...), password: str = Form(...)):
    user = get_user(email)
    if not user or not verify_password(password, user[2]):
        return HTMLResponse(LOGIN_PAGE("Invalid email or password"))
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("z_email", email) # CHANGED
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
    response.set_cookie("z_email", email) # CHANGED
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse("/")
    response.delete_cookie("z_email") # CHANGED
    return response

@app.get("/clean", response_class=HTMLResponse)
async def clean_page(request: Request):
    email = get_current_user(request)
    if not email: return RedirectResponse("/login")
    credits = get_credits(email)
    disabled = "disabled" if credits <= 0 else ""
    message = "kindly buy credits to continue" if credits <= 0 else ""
    return HTMLResponse(CLEAN_PAGE(email, credits, message, "error" if credits <= 0 else "", disabled))

@app.post("/clean", response_class=HTMLResponse)
async def clean_data(request: Request, file: UploadFile = File(None), text_data: str = Form(None)):
    email = get_current_user(request)
    if not email: return RedirectResponse("/login")
    credits = get_credits(email)
    if credits <= 0: return HTMLResponse(CLEAN_PAGE(email, 0, "kindly buy credits to continue", "error", "", "disabled"))

    try:
        df = None
        filename = "Pasted Data"
        if file and file.filename:
            filename = file.filename
            content = await file.read()
            df = pd.read_csv(io.BytesIO(content))
        elif text_data:
            df = pd.read_csv(io.StringIO(text_data))
        else:
            return HTMLResponse(CLEAN_PAGE(email, credits, "Please upload a file or paste data", "error", "", ""))

        rows = len(df)
        if rows > 5000: return HTMLResponse(CLEAN_PAGE(email, credits, "Max 5000 rows per cleaning", "error", "", ""))
        if credits < rows: return HTMLResponse(CLEAN_PAGE(email, credits, f"Not enough credits. This will cost {rows} credits. You have {credits}.", "error", "", ""))

        preview = df.head(3).to_string(index=False)
        action_log = f"Cleaned {filename} | Preview: {preview[:250]}"

        df_cleaned = smart_clean(df)
        use_credits(email, rows)
        log_activity(email, action_log, rows)
        new_credits = get_credits(email)

        csv = df_cleaned.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()
        download_link = f'<a href="data:file/csv;base64,{b64}" download="cleaned.csv" class=download>⬇️ Download Cleaned CSV</a>'
        message = f"✅ Cleaned {rows} rows from {filename}! {rows} Credits Used. You have {new_credits} left."
        return HTMLResponse(CLEAN_PAGE(email, new_credits, message, "success", download_link, ""))

    except Exception as e:
        return HTMLResponse(CLEAN_PAGE(email, credits, f"Error cleaning file: {str(e)}. Check CSV format.", "error", "", ""))

@app.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    email = get_current_user(request)
    credits = get_credits(email) if email else NEW_USER_CREDITS
    return HTMLResponse(PRICING_PAGE(email, credits))

@app.get("/checkout/{plan_key}", response_class=HTMLResponse)
async def checkout(request: Request, plan_key: str):
    email = get_current_user(request)
    if not email: return RedirectResponse("/login")
    credits = get_credits(email)
    return HTMLResponse(CHECKOUT_PAGE(email, credits, plan_key))

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
        log_activity(email, f"Purchased {credits} credits", 0)
    return RedirectResponse(url="/pricing?status=success", status_code=303)


# ===== ADMIN DASHBOARD WITH EXPORT + SET CREDITS =====
def ADMIN_PAGE(users, logs, message=""):
    total_users = len(users)
    total_credits = sum(u[3] for u in users)

    users_html = ""
    for user in users:
        user_id, user_email, _, user_credits = user
        users_html += f"""
            <tr>
                <td>{user_email}</td>
                <td class="credits">{user_credits}</td>
                <td>
                    <form action="/admin/set-credits?key={ADMIN_KEY}" method="post" style="display:inline;">
                        <input type="hidden" name="user_id" value="{user_id}">
                        <input type="number" name="amount" value="{user_credits}" min="0" style="width:90px;" placeholder="Set to">
                        <button type="submit" style="background:#00aaff;">Set</button>
                    </form>
                    <form action="/admin/add-credits?key={ADMIN_KEY}" method="post" style="display:inline;">
                        <input type="hidden" name="user_id" value="{user_id}">
                        <input type="number" name="amount" value="500" min="1" style="width:70px;" placeholder="+">
                        <button type="submit">+ Add</button>
                    </form>
                    <form action="/admin/delete-user?key={ADMIN_KEY}" method="post" style="display:inline;" onsubmit="return confirm('Delete {user_email}?')">
                        <input type="hidden" name="user_id" value="{user_id}">
                        <button type="submit" style="background:#ff4444;">Delete</button>
                    </form>
                </td>
            </tr>
        """
    
    logs_html = ""
    for log in logs[:50]:
        log_id, email, action, rows, timestamp = log
        logs_html += f"<tr><td>{timestamp}</td><td>{email}</td><td style='max-width:400px;word-break:break-word'>{action}</td><td>{rows}</td></tr>"

    return f"""<!DOCTYPE html><html><head><title>zailani Admin</title><meta name=viewport content='width=device-width, initial-scale=1.0'>
    <style>body{{font-family:Arial;background:#0a0a0a;color:#e0e0e0;padding:20px}}
.stats{{display:flex;gap:20px;margin-bottom:30px;flex-wrap:wrap}}
.card{{background:#111;padding:20px;border-radius:10px;flex:1;min-width:200px;border:1px solid #333}}
.card h2{{color:#00ff88;margin:0}}
    table{{width:100%;border-collapse:collapse;background:#111;margin-bottom:30px}}
    th,td{{padding:12px;text-align:left;border-bottom:1px solid #333;font-size:0.9em}}
    th{{background:#1a1a1a;color:#00ff88}}
.credits{{color:#00ff88;font-weight:bold}}
    input{{padding:5px;background:#222;color:#fff;border:1px solid #444;border-radius:5px;width:80px}}
    button{{padding:6px 10px;background:#00ff88;color:#000;border:none;border-radius:5px;cursor:pointer;font-weight:bold;margin-right:5px}}
.success{{color:#00ff88}}.btn-export{{background:#00aaff;color:#fff;padding:12px 20px;text-decoration:none;border-radius:8px;display:inline-block;margin-bottom:20px;font-weight:bold}}</style></head><body>
    <h1>🧹 zailani Admin</h1>
    <p class="success">{message}</p>
    <div class="stats">
        <div class="card"><h2>{total_users}</h2><p>Total Users</p></div>
        <div class="card"><h2>{total_credits}</h2><p>Total Credits Left</p></div>
    </div>
    
    <a href="/admin/export-users?key={ADMIN_KEY}" class="btn-export">📥 Export All Users CSV</a>
    
    <h2>Users</h2>
    <table><tr><th>Email</th><th>Credits</th><th>Actions</th></tr>{users_html}</table>
    
    <h2>Recent Activity - Last 50</h2>
    <table><tr><th>Time</th><th>Email</th><th>Action</th><th>Rows</th></tr>{logs_html}</table>
    </body></html>"""

@app.get("/admin/export-users")
async def export_users(request: Request):
    key = request.query_params.get("key")
    if key!= ADMIN_KEY: return HTMLResponse("401 Unauthorized", status_code=401)

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT email, credits FROM users ORDER BY id DESC")
    users = c.fetchall()
    conn.close()

    df = pd.DataFrame(users, columns=["Email", "Credits"])
    csv = df.to_csv(index=False)
    
    return StreamingResponse(io.StringIO(csv), media_type="text/csv", 
                             headers={"Content-Disposition": "attachment; filename=zailani_users.csv"})

@app.post("/admin/set-credits")
async def admin_set_credits(request: Request, user_id: int = Form(...), amount: int = Form(...)):
    key = request.query_params.get("key")
    if key!= ADMIN_KEY: return HTMLResponse("401 Unauthorized", status_code=401)

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT email FROM users WHERE id=%s", (user_id,))
    result = c.fetchone()
    if not result: return RedirectResponse(url=f"/admin?key={ADMIN_KEY}&msg=User+not+found", status_code=303)

    email = result[0]
    c.execute("UPDATE users SET credits=%s WHERE id=%s", (amount, user_id))
    log_activity(email, f"Admin set credits to {amount}", 0)
    conn.commit()
    conn.close()

    return RedirectResponse(url=f"/admin?key={ADMIN_KEY}&msg=Credits+set+to+{amount}", status_code=303)

@app.post("/admin/add-credits")
async def admin_add_credits(request: Request, user_id: int = Form(...), amount: int = Form(...)):
    key = request.query_params.get("key")
    if key!= ADMIN_KEY: return HTMLResponse("401 Unauthorized", status_code=401)

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT email, credits FROM users WHERE id=%s", (user_id,))
    result = c.fetchone()
    if not result: return RedirectResponse(url=f"/admin?key={ADMIN_KEY}&msg=User+not+found", status_code=303)

    email, credits = result
    new_credits = credits + amount
    c.execute("UPDATE users SET credits=%s WHERE id=%s", (new_credits, user_id))
    log_activity(email, f"Admin added {amount} credits", 0)
    conn.commit()
    conn.close()

    return RedirectResponse(url=f"/admin?key={ADMIN_KEY}&msg=Added+{amount}+credits", status_code=303)

@app.post("/admin/delete-user")
async def admin_delete_user(request: Request, user_id: int = Form(...)):
    key = request.query_params.get("key")
    if key!= ADMIN_KEY: return HTMLResponse("401 Unauthorized", status_code=401)

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT email FROM users WHERE id=%s", (user_id,))
    result = c.fetchone()
    if result:
        email = result[0]
        c.execute("DELETE FROM users WHERE id=%s", (user_id,))
        log_activity(email, "Account Deleted by Admin", 0)
    conn.commit()
    conn.close()

    return RedirectResponse(url=f"/admin?key={ADMIN_KEY}&msg=User+Deleted", status_code=303)