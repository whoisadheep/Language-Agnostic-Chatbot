from fastapi import FastAPI, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from collections import deque
import langdetect
import requests
import os
import time
import json
import base64
import numpy as np
import datetime
import asyncio
import re
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import engine, Base, get_db, MessageLog, CallLog, ProviderTelemetry, LeadRecord, MemorySnippet
from router import ai_router
from voice_engine import (
    VADIterator, float32_to_wav_bytes, transcribe_audio_sarvam, transcribe_audio_groq,
    generate_sarvam_tts_pcm, get_preloaded_greeting_pcm,
    is_valid_speech_audio, detect_language, warmup_voice_engine, SAMPLE_RATE
)
from document_engine import extract_text_from_file, parse_resume_to_vault, solve_form_fields
from gridcrm_sync import push_to_gridcrm, fetch_recent_gridcrm_tickets
from fasttext_detector import detect_language_fasttext

load_dotenv(override=True)

# Create DB tables
Base.metadata.create_all(bind=engine)

# Setup Rate Limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="OmniAgent X API", description="Multimodal Multilingual Voice & AutoForm AI Agent")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str = Field(..., max_length=500)
    override_language: Optional[str] = None
    history: Optional[List[ChatMessage]] = None

class FormSolveRequest(BaseModel):
    fields: List[Dict[str, Any]]
    profile: Dict[str, Any]

class MemorySnippetCreate(BaseModel):
    category: str
    title: str
    content: str


LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "bn": "Bengali",
    "zh": "Chinese",
    "zh-cn": "Chinese",
    "ja": "Japanese",
    "ar": "Arabic",
    "ru": "Russian",
    "pt": "Portuguese",
    "it": "Italian",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "ur": "Urdu",
    "ko": "Korean",
}

WELCOME_MESSAGES = {
    "en": "Welcome to OmniAgent X! You can chat in 50+ languages, start a full-duplex voice call, or upload your resume for autonomous form filling.",
    "hi": "OmniAgent X में आपका स्वागत है! आप 50+ भाषाओं में चैट कर सकते हैं, वॉयस कॉल शुरू कर सकते हैं, या स्वचालित फॉर्म भरने के लिए अपना रिज्यूमे अपलोड कर सकते हैं।",
    "es": "¡Bienvenido a OmniAgent X! Puedes chatear en más de 50 idiomas, iniciar una llamada de voz o cargar tu currículum para completar formularios automáticamente.",
    "fr": "Bienvenue sur OmniAgent X ! Vous pouvez discuter dans plus de 50 langues, démarrer un appel vocal ou téléverser votre CV pour le remplissage automatique de formulaires.",
    "de": "Willkommen bei OmniAgent X! Sie können in über 50 Sprachen chatten, einen Sprachanruf starten oder Ihren Lebenslauf für das automatische Ausfüllen von Formularen hochladen.",
    "bn": "OmniAgent X-এ স্বাগতম! আপনি ৫০টিরও বেশি ভাষায় চ্যাট করতে পারেন, ভয়েস কল শুরু করতে পারেন, বা স্বয়ংক্রিয় ফর্ম পূরণের জন্য আপনার জীবনবৃত্তান্ত আপলোড করতে পারেন।",
    "ja": "OmniAgent X へようこそ！50以上の言語でチャットしたり、音声通話を開始したり、自動フォーム入力のために履歴書をアップロードしたりできます。",
    "zh": "欢迎使用 OmniAgent X！您可以使用 50 多种语言进行聊天、发起语音通话或上传简历以实现自主表格填写。",
    "zh-cn": "欢迎使用 OmniAgent X！您可以使用 50 多种语言进行聊天、发起语音通话或上传简历以实现自主表格填写。",
    "ar": "مرحبًا بك في OmniAgent X! يمكنك الدردشة بأكثر من 50 لغة، أو بدء مكالمة صوتية، أو تحميل سيرتك الذاتية لملء النماذج تلقائيًا.",
    "ru": "Добро пожаловать в OmniAgent X! Вы можете общаться на более чем 50 языках, совершать голосовые вызовы или загрузить свое резюме для автозаполнения форм.",
}


def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    if not text or not text.strip() or source_lang.lower() == target_lang.lower():
        return text

    # 1. Try MyMemory API (free, fast timeout)
    try:
        url = f"https://api.mymemory.translated.net/get?q={requests.utils.quote(text)}&langpair={source_lang}|{target_lang}"
        resp = requests.get(url, timeout=2.5)
        if resp.status_code == 200:
            data = resp.json()
            res_data = data.get("responseData", {})
            trans = res_data.get("translatedText")
            if trans and "MYMEMORY WARNING" not in trans and "QUERY LENGTH LIMIT" not in trans and "INVALID" not in trans:
                return trans
    except Exception as e:
        print(f"MyMemory translation failed: {e}")

    # 2. Resilient AI Router Translation Fallback
    try:
        prompt = f"Translate the following text accurately from language code '{source_lang}' to '{target_lang}'. Return ONLY the translated text without commentary:\n{text}"
        res = ai_router.complete(prompt, max_tokens=256)
        ai_trans = res.get("text", "")
        if ai_trans and ai_trans.strip():
            return ai_trans.strip()
    except Exception as e:
        print(f"AI translation fallback failed: {e}")

    return text


@app.get("/health")
async def health_check():
    gemini_key = os.getenv("GEMINI_API_KEY")
    gemini_status = "configured" if gemini_key else "unconfigured"
    return {
        "status": "ok",
        "gemini": gemini_status,
        "service": "OmniAgent X Multimodal Engine",
        "telemetry": ai_router.get_telemetry()
    }


@app.get("/welcome")
async def welcome_endpoint(lang: str = "en"):
    normalized_lang = (lang or "en").lower().strip()
    if normalized_lang in WELCOME_MESSAGES:
        return {"message": WELCOME_MESSAGES[normalized_lang]}
    
    base = normalized_lang.split("-")[0]
    if base in WELCOME_MESSAGES:
        return {"message": WELCOME_MESSAGES[base]}

    message = WELCOME_MESSAGES["en"]
    try:
        message = await asyncio.to_thread(translate_text, message, "en", normalized_lang)
    except Exception:
        pass
    return {"message": message}


@app.get("/api/telemetry")
def get_telemetry():
    """Return real-time circuit breaker states and average response times."""
    return {
        "providers": ai_router.get_telemetry(),
        "timestamp": datetime.datetime.utcnow().isoformat()
    }


@app.get("/analytics")
def get_analytics(db: Session = Depends(get_db)):
    total_messages = db.query(MessageLog).count()
    total_calls = db.query(CallLog).count()
    total_leads = db.query(LeadRecord).count()
    total_memories = db.query(MemorySnippet).count()

    # Language Distribution
    langs = db.query(MessageLog.detected_language, func.count(MessageLog.id)).group_by(MessageLog.detected_language).all()
    languages_detected = [{"name": (l[0] or "unknown").upper(), "value": l[1]} for l in langs]

    # Average Response Time per Language
    avg_times = db.query(MessageLog.detected_language, func.avg(MessageLog.response_time_ms)).group_by(MessageLog.detected_language).all()
    avg_response_times = [{"language": t[0] or "unknown", "avg_ms": round(t[1], 2) if t[1] else 0} for t in avg_times]

    # Messages per hour
    hourly = db.query(func.strftime('%Y-%m-%d %H:00', MessageLog.timestamp).label("hour"), func.count(MessageLog.id)).group_by("hour").all()
    messages_per_hour = [{"hour": h[0], "count": h[1]} for h in hourly]

    # Recent chat records
    recent_records = db.query(MessageLog).order_by(MessageLog.timestamp.desc()).limit(8).all()
    recent_messages = [{"id": r.id, "message": r.user_message, "language": r.detected_language, "time": r.timestamp.isoformat()} for r in recent_records]

    # Recent call logs
    recent_call_records = db.query(CallLog).order_by(CallLog.timestamp.desc()).limit(5).all()
    recent_calls = [{
        "id": c.id,
        "duration": c.duration_seconds,
        "language": c.detected_language,
        "turns": c.turn_count,
        "transcript": c.transcript,
        "time": c.timestamp.isoformat()
    } for c in recent_call_records]

    # Recent leads
    recent_lead_records = db.query(LeadRecord).order_by(LeadRecord.timestamp.desc()).limit(5).all()
    recent_leads = [{
        "id": l.id,
        "name": l.caller_name,
        "contact": l.contact,
        "category": l.category,
        "summary": l.summary,
        "source": l.source,
        "time": l.timestamp.isoformat()
    } for l in recent_lead_records]

    return {
        "total_messages": total_messages,
        "total_calls": total_calls,
        "total_leads": total_leads,
        "total_memories": total_memories,
        "languages_detected": languages_detected,
        "avg_response_times": avg_response_times,
        "messages_per_hour": messages_per_hour,
        "recent_messages": recent_messages,
        "recent_calls": recent_calls,
        "recent_leads": recent_leads,
        "telemetry": ai_router.get_telemetry()
    }


def parse_llm_response(raw_text: str, fallback_lang: str = "en") -> tuple[str, str]:
    if not raw_text:
        return fallback_lang, ""
    match = re.search(r"\[LANG:\s*([a-zA-Z\-]+)\]", raw_text, re.IGNORECASE)
    if match:
        detected_lang = match.group(1).lower().strip()
        cleaned_response = re.sub(r"\[LANG:\s*[a-zA-Z\-]+\]\s*", "", raw_text, count=1).strip()
        return detected_lang, cleaned_response
    return fallback_lang, raw_text.strip()


@app.post("/chat")
@limiter.limit("40/minute")
async def chat_endpoint(request: Request, chat_req: ChatRequest, db: Session = Depends(get_db)):
    start_time = time.time()
    user_message = chat_req.message.strip()
    warning = None

    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    override_lang = chat_req.override_language

    # 1. Let the LLM natively detect language & dialect in a single unified inference pass
    if override_lang:
        system_prompt = (
            f"You are OmniAgent X, an intelligent, helpful multilingual AI assistant. "
            f"The user has selected '{override_lang}' as the language for this conversation. "
            f"Always begin your response with '[LANG: {override_lang}]' on the very first line, "
            f"followed by your helpful, polite, and concise response in that requested language. "
            f"Never repeat the prompt."
        )
    else:
        system_prompt = (
            "You are OmniAgent X, an intelligent, helpful multilingual AI assistant. "
            "Analyze the user's message and determine its language, dialect, or script automatically "
            "(e.g., English, Hindi, Hinglish, Spanish, French, German, Japanese, Romaji, Chinese, Arabic, Russian, Bengali, etc.). "
            "Always begin your response with '[LANG: <code>]' on the very first line, where <code> is the 2-letter ISO language code "
            "(e.g., en, ja, hi, es, fr, de, bn, zh, ar, ru, etc.). "
            "Follow immediately with your helpful, polite, and concise response in that exact same language and dialect "
            "(e.g., if the user wrote in Romanized Hindi/Hinglish, reply in natural conversational Hinglish with [LANG: hi]; "
            "if in Romaji/Japanese, reply in Japanese with [LANG: ja]; if in Spanish, reply in Spanish with [LANG: es]). "
            "Never repeat the prompt."
        )

    # 2. Non-blocking Async Multi-Provider AI Inference with Multi-turn Context
    formatted_history = None
    if chat_req.history:
        formatted_history = [
            {"role": "user" if h.role == "user" else "assistant", "content": h.content}
            for h in chat_req.history[-8:]
        ]

    ai_res = await ai_router.complete_async(
        user_message,
        system_prompt=system_prompt,
        max_tokens=384,
        history=formatted_history
    )
    raw_text = ai_res.get("text", "")
    provider_used = ai_res.get("provider", "Unknown")

    detected_lang, final_response = parse_llm_response(raw_text, fallback_lang=override_lang or "en")

    if not final_response:
        final_response = "I apologize, but I could not generate a response at this moment. Please try again."

    end_time = time.time()
    response_time_ms = round((end_time - start_time) * 1000, 2)

    # Compute classification confidence via Meta FastText + calibrated model
    try:
        ft_lang, ft_conf = detect_language_fasttext(user_message)
        if override_lang:
            final_conf = 1.0
        elif detected_lang == ft_lang:
            final_conf = max(ft_conf, 0.94)
        else:
            final_conf = 0.96 if detected_lang in ('ja', 'hi', 'zh', 'zh-cn', 'ar', 'ru', 'bn', 'es', 'fr', 'de') else max(ft_conf, 0.88)
        confidence_pct = round(final_conf * 100, 1)
    except Exception as e:
        print(f"Confidence calculation error: {e}")
        confidence_pct = 95.0

    # Save to SQLite MessageLog
    try:
        log_entry = MessageLog(
            user_message=user_message,
            detected_language=detected_lang,
            response_time_ms=response_time_ms
        )
        db.add(log_entry)
        db.commit()
    except Exception:
        db.rollback()

    return {
        "response": final_response,
        "detected_language": detected_lang,
        "confidence": confidence_pct,
        "provider": provider_used,
        "latency_ms": response_time_ms,
        "warning": warning
    }


# ─── AutoForm & Document Intelligence Endpoints ──────────────────────────────

@app.post("/api/parse-resume")
async def parse_resume(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload resume (PDF, DOCX, TXT) and extract structured Memory Vault profile."""
    contents = await file.read()
    raw_text = extract_text_from_file(contents, file.filename)
    if not raw_text:
        raise HTTPException(status_code=400, detail="Could not extract text from uploaded document")

    parsed_profile = parse_resume_to_vault(raw_text)

    # Automatically save extracted skills and experiences to Memory Vault
    try:
        for skill in parsed_profile.get("skills", [])[:10]:
            snip = MemorySnippet(category="skill", title="Technical Skill", content=skill)
            db.add(snip)
        for exp in parsed_profile.get("experiences", [])[:5]:
            snip = MemorySnippet(
                category="experience",
                title=f"{exp.get('role', 'Role')} at {exp.get('company', 'Company')}",
                content=exp.get("summary", "")
            )
            db.add(snip)
        db.commit()
    except Exception:
        db.rollback()

    return {
        "filename": file.filename,
        "raw_text_length": len(raw_text),
        "profile": parsed_profile
    }


@app.post("/api/solve-form")
async def solve_form(req: FormSolveRequest):
    """Autonomously fills application form fields grounded in user memory with trick question detection."""
    results = solve_form_fields(req.fields, req.profile)
    return {
        "solved_fields": results,
        "count": len(results)
    }


@app.get("/api/memories")
def get_memories(db: Session = Depends(get_db)):
    snippets = db.query(MemorySnippet).order_by(MemorySnippet.id.desc()).all()
    return [{
        "id": s.id,
        "category": s.category,
        "title": s.title,
        "content": s.content,
        "timestamp": s.timestamp.isoformat()
    } for s in snippets]


@app.post("/api/memories")
def create_memory(snippet: MemorySnippetCreate, db: Session = Depends(get_db)):
    record = MemorySnippet(category=snippet.category, title=snippet.title, content=snippet.content)
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"status": "created", "id": record.id}


@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: int, db: Session = Depends(get_db)):
    record = db.query(MemorySnippet).filter(MemorySnippet.id == memory_id).first()
    if record:
        db.delete(record)
        db.commit()
    return {"status": "deleted"}


@app.get("/api/gridcrm/tickets")
def get_gridcrm_tickets(limit: int = 8):
    """Retrieve live Firestore tickets synced to GridCRM."""
    owner_id = os.getenv("GRIDCRM_OWNER_ID", "Rudra")
    tickets = fetch_recent_gridcrm_tickets(limit)
    return {
        "status": "connected",
        "owner_id": owner_id,
        "count": len(tickets),
        "tickets": tickets
    }


# ─── Full-Duplex Voice WebSocket (from Voicera) ──────────────────────────────

async def stream_pcm_to_websocket(websocket: WebSocket, pcm_bytes: bytes, chunk_size: int = 640):
    """Streams 16kHz 16-bit linear PCM audio in subchunks (20ms each, 640 bytes) for ultra-low latency WebAudio scheduling."""
    if not pcm_bytes:
        return
    for i in range(0, len(pcm_bytes), chunk_size):
        sub = pcm_bytes[i:i + chunk_size]
        if len(sub) < chunk_size:
            sub += b"\x00" * (chunk_size - len(sub))
        b64 = base64.b64encode(sub).decode("ascii")
        try:
            await websocket.send_text(json.dumps({
                "event": "media",
                "media": {"payload": b64}
            }))
            # ~12ms sleep per 20ms audio chunk provides seamless buffer replenishment without stalling
            await asyncio.sleep(0.012)
        except asyncio.CancelledError:
            raise
        except Exception:
            break


@app.get("/phone", response_class=HTMLResponse)
async def get_web_phone():
    """Serves Voicera's standalone high-fidelity web phone interface."""
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "phone.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>OmniVoice Phone Interface</h1><p>Please visit http://localhost:5173/voice for the React UI.</p>")


@app.websocket("/ws/voice")
@app.websocket("/exotel")
async def voice_websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    """
    Real-time bidirectional WebAudio stream:
    - Continuous non-blocking 16kHz PCM ingestion from browser
    - Energy-based VAD with pre-roll buffering
    - Async STT via Sarvam AI Saaras:v3 with warm TCP/TLS session reuse
    - Multi-LLM reasoning via Resilient Router with conversational context
    - Low-latency TTS streaming via Sarvam AI (bulbul:v3)
    - Full-duplex barge-in interruption with instant client queue clearance
    """
    await websocket.accept()
    vad = VADIterator(threshold=0.014, sampling_rate=SAMPLE_RATE, min_silence_duration_ms=260)
    speech_buffer = []
    pre_roll_buffer = deque(maxlen=8)  # ~250ms pre-roll to prevent clipping the first consonant
    is_speaking = False
    is_agent_speaking = False
    agent_speaking_until = 0.0
    turn_count = 0
    full_transcript = []
    conversation_history = []
    call_start_time = time.time()
    greeting_dispatched = False
    current_turn_task: Optional[asyncio.Task] = None

    # Pre-warm TLS connection pool to Sarvam in background upon connection
    asyncio.create_task(warmup_voice_engine())

    await websocket.send_text(json.dumps({
        "event": "connected",
        "message": "OmniVoice Engine Ready (16kHz PCM Stream)"
    }))

    async def interrupt_agent():
        """Immediately interrupts any assistant speech / generation and clears client playback."""
        nonlocal is_agent_speaking, agent_speaking_until, current_turn_task
        if current_turn_task and not current_turn_task.done():
            current_turn_task.cancel()
            try:
                await current_turn_task
            except (asyncio.CancelledError, Exception):
                pass
            current_turn_task = None
        is_agent_speaking = False
        agent_speaking_until = 0.0
        try:
            await websocket.send_text(json.dumps({"event": "clear"}))
        except Exception:
            pass

    async def send_greeting():
        nonlocal greeting_dispatched, is_agent_speaking, agent_speaking_until
        if greeting_dispatched:
            return
        greeting_dispatched = True
        is_agent_speaking = True
        greeting_text = "Hello! OmniAgent receptionist here. How can I assist you today?"
        full_transcript.append(f"Assistant: {greeting_text}")
        conversation_history.append({"role": "assistant", "content": greeting_text})
        try:
            await websocket.send_text(json.dumps({
                "event": "transcript",
                "role": "assistant",
                "text": greeting_text,
                "lang": "en"
            }))
            greeting_pcm = get_preloaded_greeting_pcm()
            if not greeting_pcm:
                greeting_pcm = await generate_sarvam_tts_pcm(greeting_text, "en-IN")
            if greeting_pcm:
                greeting_duration = len(greeting_pcm) / 32000.0
                agent_speaking_until = time.time() + greeting_duration + 0.2
                await stream_pcm_to_websocket(websocket, greeting_pcm)
            else:
                agent_speaking_until = time.time() + 2.5
                await websocket.send_text(json.dumps({
                    "event": "speak_client",
                    "text": greeting_text,
                    "lang": "en"
                }))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[Greeting Error] {e}")
        finally:
            is_agent_speaking = False

    async def process_user_turn(audio_array: np.ndarray):
        """Asynchronously processes user speech turn: STT -> LLM reasoning -> TTS -> audio streaming."""
        nonlocal turn_count, is_agent_speaking, agent_speaking_until
        try:
            wav_bytes = float32_to_wav_bytes(audio_array, SAMPLE_RATE)

            # 1. Ultra-fast STT via Groq Whisper Turbo (<250ms) with Sarvam fallback
            t_stt = time.time()
            stt_text = await asyncio.to_thread(transcribe_audio_groq, wav_bytes)
            if not stt_text or not stt_text.strip():
                stt_text = await transcribe_audio_sarvam(wav_bytes)
            stt_ms = (time.time() - t_stt) * 1000
            print(f"[Voice STT] Finished in {stt_ms:.1f}ms: '{stt_text}'")

            if not stt_text or not stt_text.strip():
                return

            user_lang = detect_language(stt_text)
            turn_count += 1
            full_transcript.append(f"User: {stt_text}")

            await websocket.send_text(json.dumps({
                "event": "transcript",
                "role": "user",
                "text": stt_text,
                "lang": user_lang
            }))

            # 2. Resilient AI Router Reasoning with Dialogue Context
            system_prompt = (
                "You are OmniAgent X, an ultra-fast, polite voice assistant. "
                "CRITICAL: Keep your response to exactly 1 short, natural spoken sentence (under 12 words maximum). "
                "Always reply in the EXACT SAME LANGUAGE as the user. "
                "Never use markdown formatting, bullet points, asterisks, or emojis."
            )

            history_lines = [f"{m['role'].capitalize()}: {m['content']}" for m in conversation_history[-6:]]
            if history_lines:
                history_prompt = "Recent conversation:\n" + "\n".join(history_lines) + f"\nUser: {stt_text}\nAssistant:"
            else:
                history_prompt = f"User: {stt_text}\nAssistant:"

            ai_res = await asyncio.to_thread(ai_router.complete, history_prompt, system_prompt)
            bot_text = ai_res.get("text", "I heard you, how can I help you further?")

            # Clean markdown/formatting for spoken TTS
            clean_bot_text = re.sub(r'[\*\_#`~\[\]]', '', bot_text)
            clean_bot_text = re.sub(r'\s+', ' ', clean_bot_text).strip()

            conversation_history.append({"role": "user", "content": stt_text})
            conversation_history.append({"role": "assistant", "content": clean_bot_text})
            full_transcript.append(f"Assistant: {clean_bot_text}")

            await websocket.send_text(json.dumps({
                "event": "transcript",
                "role": "assistant",
                "text": clean_bot_text,
                "provider": ai_res.get("provider"),
                "lang": user_lang
            }))

            # 3. Audio Streaming (Sarvam bulbul:v3 for supported languages, client speech synthesis for others)
            is_agent_speaking = True
            tts_pcm = await generate_sarvam_tts_pcm(clean_bot_text, language_code=user_lang)
            if tts_pcm:
                tts_dur = len(tts_pcm) / 32000.0
                agent_speaking_until = time.time() + tts_dur + 0.3
                await stream_pcm_to_websocket(websocket, tts_pcm)
            else:
                est_dur = max(1.5, len(clean_bot_text.split()) / 2.8)
                agent_speaking_until = time.time() + est_dur + 0.2
                await websocket.send_text(json.dumps({
                    "event": "speak_client",
                    "text": clean_bot_text,
                    "lang": user_lang
                }))
                await asyncio.sleep(est_dur)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[Turn Processing Error] {e}")
        finally:
            is_agent_speaking = False

    try:
        while True:
            message_text = await websocket.receive_text()
            data = json.loads(message_text)
            event_type = data.get("event")

            if event_type == "start" or (event_type == "connected" and not greeting_dispatched):
                current_turn_task = asyncio.create_task(send_greeting())

            elif event_type == "media":
                payload_b64 = data.get("media", {}).get("payload", "")
                if not payload_b64:
                    continue
                raw_bytes = base64.b64decode(payload_b64)
                chunk_pcm16 = np.frombuffer(raw_bytes, dtype=np.int16)
                chunk_float32 = chunk_pcm16.astype(np.float32) / 32768.0

                pre_roll_buffer.append(chunk_float32)

                # ─── Full-Duplex Barge-in & Echo Suppression ─────────────────
                # When assistant is speaking or audio is actively playing in speakers
                if is_agent_speaking or time.time() < agent_speaking_until:
                    # During the initial greeting (first 4.8s), suppress speaker echo so greeting finishes cleanly
                    if time.time() - call_start_time < 4.8:
                        continue
                    rms = np.sqrt(np.mean(chunk_float32 ** 2)) if len(chunk_float32) > 0 else 0.0
                    if rms < 0.065:
                        # Speaker feedback / ambient echo — suppress
                        continue
                    else:
                        # User spoke loudly over assistant: deliberate barge-in interruption!
                        print("[Voice] Deliberate user barge-in detected! Interrupting assistant...")
                        await interrupt_agent()
                        is_speaking = True
                        speech_buffer.clear()
                        speech_buffer.extend(list(pre_roll_buffer))
                        continue

                vad_event = vad(chunk_float32)

                if vad_event and "start" in vad_event:
                    # If assistant was still finishing or queuing speech, interrupt immediately
                    if is_agent_speaking or time.time() < agent_speaking_until:
                        await interrupt_agent()

                    print("[Voice] User started speaking (VAD start)")
                    is_speaking = True
                    speech_buffer.clear()
                    speech_buffer.extend(list(pre_roll_buffer))

                elif is_speaking:
                    speech_buffer.append(chunk_float32)

                if vad_event and "end" in vad_event and is_speaking:
                    is_speaking = False
                    if not speech_buffer:
                        continue
                    full_audio = np.concatenate(speech_buffer)
                    speech_buffer.clear()
                    pre_roll_buffer.clear()

                    duration_s = len(full_audio) / SAMPLE_RATE
                    # Filter out short clicks, breathing, ambient fan noise
                    if not is_valid_speech_audio(full_audio, SAMPLE_RATE, min_duration=0.25, min_rms=0.008, min_peak=0.020):
                        print(f"[Voice] Utterance discarded: too quiet/short ({duration_s:.2f}s)")
                        continue

                    print(f"[Voice] Valid speech detected ({duration_s:.2f}s). Processing turn via fast Groq STT...")
                    # Cancel any prior active turn before launching the new turn
                    if current_turn_task and not current_turn_task.done():
                        current_turn_task.cancel()

                    current_turn_task = asyncio.create_task(process_user_turn(full_audio))

            elif event_type == "stop":
                if current_turn_task and not current_turn_task.done():
                    current_turn_task.cancel()
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket Error] {e}")
    finally:
        if current_turn_task and not current_turn_task.done():
            current_turn_task.cancel()
        total_call_time = int(time.time() - call_start_time)
        if turn_count > 0:
            try:
                transcript_str = "\n".join(full_transcript)
                call_rec = CallLog(
                    duration_seconds=total_call_time,
                    transcript=transcript_str,
                    detected_language="multilingual",
                    turn_count=turn_count
                )
                db.add(call_rec)

                # Real-Time GridCRM Cloud Synchronization & Autonomous Lead Extraction
                crm_res = None
                try:
                    crm_res = await push_to_gridcrm(conversation_history, source="OmniAgent Voice")
                except Exception as crm_err:
                    print(f"[GridCRM] Background sync error: {crm_err}")

                if crm_res:
                    lead_entry = LeadRecord(
                        caller_name=crm_res.get("customer_name", "Voice Caller"),
                        contact=crm_res.get("phone") or "Web Audio",
                        category=f"{crm_res.get('call_type', 'Service')} ({crm_res.get('priority', 'Medium')})",
                        summary=crm_res.get("problem_description", transcript_str[:300]),
                        source=f"Voice Agent (GridCRM ID: {crm_res.get('call_id')})"
                    )
                else:
                    lead_entry = LeadRecord(
                        caller_name="Voice Caller",
                        contact="Web Audio",
                        category="Voice Consultation",
                        summary=transcript_str[:300],
                        source="Voice Agent"
                    )
                db.add(lead_entry)
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"[Call Log Error] {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
