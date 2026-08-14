from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os
import pandas as pd
import io

app = FastAPI(title="TruthGuard AI")

# FORCE PATH - This fixes TemplateNotFound
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

USER_CREDITS = 100

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="home.html", 
        context={"credits": USER_CREDITS}
    )

@app.get("/clean", response_class=HTMLResponse)
async def clean_page(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="clean.html", 
        context={"credits": USER_CREDITS, "error": None}
    )

@app.post("/clean", response_class=HTMLResponse)
async def clean_data(request: Request, file: UploadFile = File(None), text_data: str = Form(None)):
    global USER_CREDITS
    if USER_CREDITS <= 0:
        return templates.TemplateResponse(request=request, name="clean.html", context={"credits": USER_CREDITS, "error": "Kindly buy credits to continue"})
    USER_CREDITS -= 1
    return templates.TemplateResponse(request=request, name="clean.html", context={"credits": USER_CREDITS, "error": "✅ Cleaned successfully! 1 credit used."})

@app.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    return templates.TemplateResponse(request=request, name="pricing.html", context={"credits": USER_CREDITS})

@app.post("/pay")
async def pay(plan: str = Form(...)):
    global USER_CREDITS
    USER_CREDITS += int(plan)
    return RedirectResponse(url="/pricing", status_code=303)