from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(
    title="TruthGuard AI",
    description="AI-Powered Fact Checking API. Verify any claim instantly with Groq LLM.",
    version="1.1.0",
    contact={"name": "Musa Zailani", "email": "zailaniheman@gmail.com"}
)

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TruthGuard AI - by Musa Zailani</title>
        <style>
            body {font-family: Arial; background: #0f172a; color: white; text-align: center; padding: 60px 20px;}
            h1 {font-size: 52px; color: #38bdf8; margin: 0;}
            .subtitle {font-size: 22px; margin: 10px 0 30px;}
            .btn {background: #38bdf8; color: #0f172a; padding: 16px 32px; text-decoration: none; border-radius: 10px; font-weight: bold; font-size: 18px;}
            .btn:hover {background: #0ea5e9;}
            .footer {margin-top: 60px; opacity: 0.6; font-size: 14px;}
        </style>
    </head>
    <body>
        <h1>TruthGuard AI</h1>
        <p class="subtitle">Fact Checking by <b>Musa Zailani</b></p>
        <p>Verify any claim instantly with AI. Get verdict: GROUNDED, CONTRADICTED, or UNCERTAIN.</p>
        <br>
        <a href="/docs" class="btn">Try it Free →</a>
        <div class="footer">
            Founder: Musa Zailani | Contact: zailaniheman@gmail.com | Status: LIVE
        </div>
    </body>
    </html>
    """

@app.get("/health")
def health():
    return {"status": "LIVE", "founder": "Musa Zailani"}