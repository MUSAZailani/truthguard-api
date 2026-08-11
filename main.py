import os
import requests
import json
import re
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import io
from reportlab.pdfgen import canvas # For PDF export

app = FastAPI(title="TruthGuard AI v4.0", version="4.0.0")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
CREDITS = 1000

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
    global CREDITS
    if CREDITS <= 0: return [{"error": "No credits left. Please buy more."}]
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    prompt = f"""Process each line. Return ONE JSON array.
    RULES: 'cleaned' MUST be factually correct. 'verdict' = True, False, or Partially True
    Format: [{{"original":"...", "cleaned":"...", "verdict":"...", "explanation":"..."}}]
    Lines: {text}"""
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "temperature": 0.0}
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    ai_response = r.json()["choices"][0]["message"]["content"]
    results = parse_ai_response(ai_response)
    CREDITS -= len(results)
    return results

def navbar():
    return """
    <div style="background:#111; padding:15px; display:flex; justify-content:center; gap:30px; border-bottom:2px solid #00FF88">
        <a href="/" style="color:#00FF88; text-decoration:none; font-weight:bold; font-size:18px">Home</a>
        <a href="/cleaner" style="color:#fff; text-decoration:none; font-weight:bold; font-size:18px">Data Cleaner</a>
        <a href="/pricing" style="color:#fff; text-decoration:none; font-weight:bold; font-size:18px">Pricing</a>
    </div>
    """

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(content=f"""
    <html><head><title>TruthGuard AI</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>body{{font-family:Arial;background:#0a0a0a;color:#fff;text-align:center;padding:50px}}
    h1{{color:#00FF88;font-size:48px}}.btn{{padding:20px 40px;background:#00FF88;color:#000;border:none;border-radius:12px;font-size:20px;font-weight:bold;cursor:pointer;margin:10px}}</style>
    </head><body>
    {navbar()}
    <h1>TruthGuard AI</h1>
    <p style="font-size:22px">Batch Data Cleaning + Fact Checking for Enterprises</p>
    <p>Upload 1000s of rows. Fix typos. Verify facts. Export clean data.</p>
    <a href="/cleaner"><button class="btn">Start Cleaning Data</button></a>
    <a href="/pricing"><button class="btn" style="background:#00C3FF">View Pricing</button></a>
    </body></html>
    """)

@app.get("/cleaner", response_class=HTMLResponse)
def cleaner():
    return HTMLResponse(content=f"""
    <html><head><title>Data Cleaner</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>body{{font-family:Arial;background:#0a0a0a;color:#fff;padding:20px;text-align:center}}
   .credit-bar{{background:#111;padding:15px;border-radius:12px;margin:20px auto;border:2px solid #00FF88;width:90%}}
    textarea{{width:90%;height:150px;background:#1a1a1a;color:#fff;border:1px solid #333;padding:10px;border-radius:8px}}
   .btn{{padding:18px;border:none;border-radius:12px;font-weight:bold;margin:8px;cursor:pointer;width:90%;font-size:18px}}
   .green{{background:#00FF88;color:#000}}.blue{{background:#00C3FF;color:#000}}.yellow{{background:#FFC107;color:#000}}
    #result{{margin-top:20px;text-align:left}}
   .result-card{{background:#1a1a1a;padding:15px;border-radius:8px;margin-bottom:15px;border-left:4px solid #00C3FF}}
   .verdict-true{{color:#00FF88;font-weight:bold}}.verdict-false{{color:#FF4444;font-weight:bold}}.verdict-partial{{color:#FFC107;font-weight:bold}}</style>
    </head><body>
    {navbar()}
    <h1>Data Cleaner</h1>
    <div class="credit-bar"><h2>Credits Left: <span id="credits">{CREDITS}</span></h2></div>
    <h3>Option 1: Paste Data</h3>
    <textarea id="claims" placeholder="Paste multiple claims. One per line."></textarea><br>
    <button class="btn green" onclick="cleanData()">Clean Text</button>
    <h3>Option 2: Upload CSV</h3>
    <input type="file" id="csvFile" accept=".csv,.txt" style="margin:10px">
    <button class="btn blue" onclick="uploadCSV()">Upload & Clean CSV</button>
    <h3>Export Results</h3>
    <button class="btn yellow" onclick="downloadCSV()">Download CSV</button>
    <button class="btn" style="background:#FF4444;color:#fff" onclick="downloadPDF()">Download PDF</button>
    <button class="btn" style="background:#00C3FF;color:#000" onclick="downloadExcel()">Download Excel</button>
    <div id="result"></div>
    <script>
    let lastResults = [];
    async function cleanData() {{
        const data = document.getElementById('claims').value;
        if(!data) return alert('Paste some data first');
        await processAndDisplay(data);
    }}
    async function uploadCSV() {{
        const file = document.getElementById('csvFile').files[0];
        if(!file) return alert('Select a file');
        const text = await file.text();
        await processAndDisplay(text);
    }}
    async function processAndDisplay(data) {{
        document.getElementById('result').innerHTML = '<p>Cleaning... This may take 1-2 mins</p>';
        const res = await fetch('/clean', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{data:data}})}});
        const jsonArray = await res.json();
        lastResults = jsonArray;
        let html = '';
        jsonArray.forEach(item => {{
            if(item.error) {{ html = `<p style="color:red">${{item.error}}</p>`; return; }}
            let verdictClass = item.verdict === 'True'? 'verdict-true' : item.verdict === 'False'? 'verdict-false' : 'verdict-partial';
            html += `<div class="result-card"><b>Original:</b> ${{item.original}}<br><br><b>Cleaned:</b> ${{item.cleaned}}<br><br><b>Verdict:</b> <span class="${{verdictClass}}">${{item.verdict}}</span><br><br><b>Explanation:</b> ${{item.explanation}}</div>`;
        }});
        document.getElementById('result').innerHTML = html;
        document.getElementById('credits').innerText = {CREDITS} - jsonArray.length;
    }}
    function downloadCSV() {{
        if(lastResults.length === 0) return alert('Clean some data first');
        let csv = 'Original,Cleaned,Verdict,Explanation\\n';
        lastResults.forEach(r => {{ csv += `"${{r.original}}","${{r.cleaned}}","${{r.verdict}}","${{r.explanation}}"\\n`; }});
        const blob = new Blob([csv], {{type: 'text/csv'}});
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = 'truthguard_results.csv'; a.click();
    }}
    function downloadPDF() {{
        if(lastResults.length === 0) return alert('Clean some data first');
        fetch('/export_pdf', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{data:lastResults}})}})
       .then(res => res.blob()).then(blob => {{
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a'); a.href = url; a.download = 'truthguard_results.pdf'; a.click();
        }});
    }}
    function downloadExcel() {{ alert('Excel export coming in v4.1'); }}
    </script>
    </body></html>
    """)

@app.get("/pricing", response_class=HTMLResponse)
def pricing():
    return HTMLResponse(content=f"""
    <html><head><title>Pricing</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>body{{font-family:Arial;background:#0a0a0a;color:#fff;text-align:center;padding:20px}}
   .plan{{background:#111;border:2px solid #333;padding:30px;border-radius:12px;margin:20px auto;width:90%;max-width:400px}}
   .plan h3{{color:#00C3FF;font-size:24px}}.btn{{padding:18px;border:none;border-radius:12px;font-weight:bold;margin-top:12px;cursor:pointer;width:100%;font-size:18px;background:#00FF88;color:#000}}</style>
    </head><body>
    {navbar()}
    <h1>Choose Your Plan</h1>
    <div class="plan"><h3>Starter</h3><p><b>₦7,500</b> for 500 credits</p><button class="btn" onclick="pay(7500,500)">Pay ₦7,500</button></div>
    <div class="plan" style="border:2px solid #00FF88"><h3>Growth - MOST POPULAR</h3><p><b>₦75,000</b> for 10,000 credits</p><button class="btn" onclick="pay(75000,10000)">Pay ₦75,000</button></div>
    <div class="plan"><h3>Enterprise</h3><p><b>₦150,000</b> for 20,000 credits</p><button class="btn" onclick="pay(150000,20000)">Pay ₦150,000</button></div>
    <script src="https://js.paystack.co/v1/inline.js"></script>
    <script>
    function pay(amount, credits) {{
      var handler = PaystackPop.setup({{
        key: 'pk_test_b89a61386411b3b47b79d402555417e1b333261c',
        email: 'customer@example.com', amount: amount * 100, currency: 'NGN', ref: 'TG_' + Date.now(),
        callback: function(response){{ alert('Payment Successful! ' + credits.toLocaleString() + ' credits added.'); }},
        onClose: function(){{ alert('Payment cancelled'); }}
      }});
      handler.openIframe();
    }}
    </script>
    </body></html>
    """)

@app.post("/clean")
def clean(req: CleanRequest):
    try: return JSONResponse(content=clean_with_groq(req.data))
    except Exception as e: return JSONResponse(content=[{"original": req.data, "cleaned": "", "verdict": "Error", "explanation": str(e)}])

@app.post("/export_pdf")
def export_pdf(req: CleanRequest):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.setFont("Helvetica", 10)
    y = 800
    for item in req.data:
        p.drawString(50, y, f"Original: {item['original']}")
        y -= 15
        p.drawString(50, y, f"Cleaned: {item['cleaned']}")
        y -= 15
        p.drawString(50, y, f"Verdict: {item['verdict']}")
        y -= 25
        if y < 50: p.showPage(); y = 800
    p.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=truthguard_results.pdf"})