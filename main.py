from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os
import pandas as pd
import io

app = FastAPI(title="TruthGuard AI")
templates = Jinja2Templates(directory="templates")

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
async def clean_data(
    request: Request,
    file: UploadFile = File(None),
    text_data: str = Form(None)
):
    global USER_CREDITS
    
    if USER_CREDITS <= 0:
        return templates.TemplateResponse(
            request=request, 
            name="clean.html", 
            context={"credits": USER_CREDITS, "error": "Kindly buy credits to continue"}
        )
    
    try:
        if file:
            content = await file.read()
            df = pd.read_csv(io.StringIO(content.decode('utf-8')))
            rows = len(df)
        elif text_data:
            rows = len(text_data.splitlines())
        else:
            raise ValueError("Please upload a file or paste data")
        
        USER_CREDITS -= 1
        
        return templates.TemplateResponse(
            request=request, 
            name="clean.html", 
            context={"credits": USER_CREDITS, "error": f"✅ Cleaned {rows} rows successfully! 1 credit used."}
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            request=request, 
            name="clean.html", 
            context={"credits": USER_CREDITS, "error": f"Error: {str(e)}"}
        )

@app.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="pricing.html", 
        context={"credits": USER_CREDITS}
    )

@app.post("/pay")
async def pay(plan: str = Form(...)):
    global USER_CREDITS
    USER_CREDITS += int(plan)
    return RedirectResponse(url="/pricing", status_code=303)