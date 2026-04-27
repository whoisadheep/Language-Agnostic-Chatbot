from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field
from typing import Optional
import langdetect
import requests
import os
import time
from dotenv import load_dotenv
from google import genai
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import engine, Base, get_db, MessageLog

load_dotenv()

# Create DB tables
Base.metadata.create_all(bind=engine)

# Setup Rate Limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Allow CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY is not set in .env")

# Initialize Gemini Client
try:
    if GEMINI_API_KEY:
        client = genai.Client(api_key=GEMINI_API_KEY)
    else:
        client = None
except Exception as e:
    client = None
    print(f"Failed to initialize Gemini Client: {e}")

class ChatRequest(BaseModel):
    message: str = Field(..., max_length=500)
    override_language: Optional[str] = None

def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    url = "https://libretranslate.com/translate"
    payload = {
        "q": text,
        "source": source_lang,
        "target": target_lang,
        "format": "text"
    }
    headers = {
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()
    return data.get("translatedText", text)

@app.get("/health")
async def health_check():
    health_status = {"status": "ok", "gemini": "unconfigured"}
    global client
    if client:
         health_status["gemini"] = "configured"
    else:
         current_key = os.getenv("GEMINI_API_KEY")
         if current_key:
             health_status["gemini"] = "configured (lazy)"
    return health_status

@app.get("/welcome")
async def welcome_endpoint(lang: str = "en"):
    message = "Welcome to OmniLingua! Type a message in any language, and the AI will respond in the same language."
    if lang != "en":
        try:
            message = translate_text(message, "en", lang)
        except Exception as e:
            print(f"Welcome translation failed: {e}")
            pass
    return {"message": message}

@app.get("/analytics")
def get_analytics(db: Session = Depends(get_db)):
    total_messages = db.query(MessageLog).count()
    
    # Language Distribution
    langs = db.query(MessageLog.detected_language, func.count(MessageLog.id)).group_by(MessageLog.detected_language).all()
    languages_detected = [{"name": l[0], "value": l[1]} for l in langs]
    
    # Average Response Time per Language
    avg_times = db.query(MessageLog.detected_language, func.avg(MessageLog.response_time_ms)).group_by(MessageLog.detected_language).all()
    avg_response_times = [{"language": t[0], "avg_ms": round(t[1], 2) if t[1] else 0} for t in avg_times]
    
    # Messages per hour
    # SQLite strftime %H is hour, we can extract just the hour or full Y-m-d H
    hourly = db.query(func.strftime('%Y-%m-%d %H:00', MessageLog.timestamp).label("hour"), func.count(MessageLog.id)).group_by("hour").all()
    messages_per_hour = [{"hour": h[0], "count": h[1]} for h in hourly]
    
    # Recent live feed
    recent_records = db.query(MessageLog).order_by(MessageLog.timestamp.desc()).limit(10).all()
    recent_messages = [{"id": r.id, "message": r.user_message, "language": r.detected_language, "time": r.timestamp.isoformat()} for r in recent_records]

    return {
        "total_messages": total_messages,
        "languages_detected": languages_detected,
        "avg_response_times": avg_response_times,
        "messages_per_hour": messages_per_hour,
        "recent_messages": recent_messages
    }

@app.post("/chat")
@limiter.limit("20/minute")
async def chat_endpoint(request: Request, chat_req: ChatRequest, db: Session = Depends(get_db)):
    start_time = time.time()
    user_message = chat_req.message
    warning = None
    
    if not user_message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
        
    try:
        # 1. Detect Language
        detected_lang = chat_req.override_language
        if not detected_lang:
            try:
                detected_lang = langdetect.detect(user_message)
                print(f"Detected language: {detected_lang}")
            except Exception as e:
                print(f"Language detection failed: {e}")
                detected_lang = "en"
                warning = "language_detection_failed"
        else:
            print(f"Override language: {detected_lang}")

        # 2. Translate to English if needed
        english_message = user_message
        if detected_lang != "en":
            try:
                english_message = translate_text(user_message, detected_lang, "en")
            except Exception as e:
                print(f"Translation API down: {e}")
                warning = "translation_api_down"
                english_message = user_message
            
        # 3. Call Gemini
        global client
        if not client:
            load_dotenv(override=True)
            current_key = os.getenv("GEMINI_API_KEY")
            if current_key:
                client = genai.Client(api_key=current_key)
            else:
                raise HTTPException(status_code=500, detail="Gemini Client is not configured. Please set GEMINI_API_KEY in .env")
             
        response = client.models.generate_content(model='gemini-2.5-flash', contents=english_message)
        gemini_response = response.text
        
        # 4. Translate back if original language was not English
        final_response = gemini_response
        if detected_lang != "en" and warning != "translation_api_down":
            try:
                final_response = translate_text(gemini_response, "en", detected_lang)
            except Exception as e:
                print(f"Translation API down during response: {e}")
                warning = "translation_api_down"
            
        end_time = time.time()
        response_time_ms = (end_time - start_time) * 1000

        # Log to Database
        try:
            log_entry = MessageLog(
                user_message=user_message,
                detected_language=detected_lang,
                response_time_ms=response_time_ms
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            print(f"Failed to save analytics: {e}")
            db.rollback()

        return {
            "response": final_response,
            "detected_language": detected_lang,
            "warning": warning
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
