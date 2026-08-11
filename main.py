import os
import requests
import json
import re
import csv
import io
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

app = FastAPI(title="TruthGuard AI v4.2")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
CREDITS = 1000
lastResults = []

class CleanRequest(BaseModel):
    data: str

def parse_ai_response(text):
    try: return json.loads(text)
    except:
        objects = re.findall(r'\{.*?\}', text, re.DOTALL)
        results = []
        for obj_str in objects:
            try: results.append(json.loads(obj_str))
            except: continue
        return results if results else [{"original": text, "cleaned": "Parse Error", "verdict": "Error", "explanation": "Could not parse"}]

def clean_with_groq(text):
    global CREDITS, lastResults
    if CREDITS <= 0: return [{"error": "No credits left. Please buy more on Pricing page."}]
    if not GROQ_API_KEY: return [{"error": "GROQ_API_KEY not set in Railway"}]

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    prompt = f"""Process each line as a CSV row with 5 columns: Product_Name, Price, Supplier, Category, Stock. Return ONE JSON array. RULES: 'cleaned' MUST be a comma-separated CSV row with the 5 columns fixed. 'verdict' = True, False, or Partially True. Format: [{{"original":"...", "cleaned":"...", "verdict":"...", "explanation":"..."}}] Lines: {text}"""
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "temperature": 0.0}
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    ai_response = r.json()["choices"][0]["message"]["content"]
    results = parse_ai_response(ai_response)
    CREDITS -= len(results)
    lastResults = results
    return results

def get_nav(active):
    return f"""
    <div class="nav">
        <a href="/" class="{'active' if active=='home' else ''}">Home</a>
        <a href="/pricing" class="{'active' if active=='pricing' else ''}">Pricing</a>
    </div>
    """

def get_style():
    return """
    <style>
        body { font-family: Arial; background: #0a0a0a; color: #fff; padding: 20px; text-align: center; }
     .nav { display:flex; justify-content:center; gap:40px; margin-bottom:20px; border-bottom:2px solid #00FF88; padding-bottom:10px }
     .nav a { color:#888; text-decoration:none; font-weight:bold; font-size:18px }
     .nav a.active { color:#00FF88 }
        h1 { color:#00FF88; font-size:42px; margin:10px 0 }
     .credit-bar { background:#111; padding:15px; border-radius:12px; margin:20px auto; border:2px solid #00FF88; max-width:400px }
     .credit-bar h2 { color:#00FF88; margin:0 }
        textarea { width: 90%; height: 150px; background: #1a1a1a; color: #fff; border: 1px solid #333; padding: 10px; border-radius: 8px; font-size:16px; max-width:600px }
     .btn { padding: 18px; border: none; border-radius: 12px; font-weight: bold; margin: 8px; cursor: pointer; width: 90%; font-size:18px; max-width:400px }
     .green { background: #00FF88; color: #000; }.blue { background: #00C3FF; color: #000; }.yellow { background:#FFC107;color:#000 }.purple { background:#A855F7;color:#fff }
     .plan { background: #111; border: 2px solid #333; padding: 25px; border-radius: 12px; margin: 15px auto; width: 90%; max-width:400px; text-align:left }
        #result { margin-top:20px; text-align:left; max-width:800px; margin-left:auto; margin-right:auto }
     .result-card { background:#1a1a1a; padding:15px; border-radius:8px; margin-bottom:15px; font-size:14px; line-height:1.6; border-left: 4px solid #00C3FF }
     .verdict-true { color:#00FF88; font-weight:bold }.verdict-false { color:#FF4444; font-weight:bold }.verdict-partial { color:#FFC107; font-weight:bold }
    </style>
    """

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(content=f"""
    <html><head><title>TruthGuard AI - Cleaner</title><meta name="viewport" content="width=device-width, initial-scale=1.0">{get_style()}</head>
    <body>
        {get_nav('home')}
        <h1>TruthGuard<br>AI</h1>
        <p style="font-size:18px">Batch Data Cleaning +<br>Fact Checking for Enterprises</p>
        <p>Upload 1000s of rows. Fix typos.<br>Verify facts.