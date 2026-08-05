from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import httpx

app = FastAPI(title="TruthGuard API v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

class ClaimRequest(BaseModel):
    claim: str

@app.get("/")
def read_root():
    return {"status": "TruthGuard v2 Running", "model": "llama-3.1-8b-instant"}

@app.post("/fact-check")
async def fact_check(request: ClaimRequest):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not set")
    
    prompt = f"""You are TruthGuard, an AI that detects misinformation.
    Analyze this claim: "{request.claim}"
    
    Return ONLY valid JSON:
    {{
      "claim": "{request.claim}",
      "verdict": "True" or "False" or "Misleading" or "Unverified",
      "confidence": 0.0 to 1.0,
      "explanation": "2-3 sentences explaining why",
      "sources": ["suggest 2 reputable sources to check"]
    }}
    Be factual. If unsure say Unverified."""
    
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 400
            },
            timeout=30.0
        )
    
    return {"result": r.json()["choices"][0]["message"]["content"]}
