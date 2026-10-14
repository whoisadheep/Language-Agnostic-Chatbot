from fastapi import FastAPI, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import langdetect
import requests
import os
import time
import json
import base64
import numpy as np
import datetime
import asyncio
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import engine, Base, get_db, MessageLog, CallLog, ProviderTelemetry, LeadRecord, MemorySnippet
from router import ai_router
from voice_engine import VADIterator, float32_to_wav_bytes, transcribe_audio_groq, generate_sarvam_tts_pcm, get_preloaded_greeting_pcm, is_valid_speech_audio, SAMPLE_RATE
from document_engine import extract_text_from_file, parse_resume_to_vault, solve_form_fields

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

class ChatRequest(BaseModel):
    message: str = Field(..., max_length=500)
    override_language: Optional[str] = None

class FormSolveRequest(BaseModel):
    fields: List[Dict[str, Any]]
    profile: Dict[str, Any]

class MemorySnippetCreate(BaseModel):
    category: str
    title: str
    content: str


def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    if not text or not text.strip() or source_lang.lower() == target_lang.lower():
        return text

    # 1. Try MyMemory API (free, reliable)
    try:
        url = f"https://api.mymemory.translated.net/get?q={requests.utils.quote(text)}&langpair={source_lang}|{target_lang}"
        resp = requests.get(url, timeout=5)
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
        res = ai_router.complete(prompt)
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
    message = "Welcome to OmniAgent X! You can chat in 50+ languages, start a full-duplex voice call, or upload your resume for autonomous form filling."
    if lang != "en":
        try:
            message = translate_text(message, "en", lang)
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


@app.post("/chat")
@limiter.limit("40/minute")
async def chat_endpoint(request: Request, chat_req: ChatRequest, db: Session = Depends(get_db)):
    start_time = time.time()
    user_message = chat_req.message.strip()
    warning = None

    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # 1. Language Detection
    detected_lang = chat_req.override_language
    if not detected_lang:
        try:
            detected_lang = langdetect.detect(user_message)
        except Exception:
            detected_lang = "en"
            warning = "language_detection_failed"

    # 2. English normalization for deep prompt reasoning
    english_message = user_message
    if detected_lang != "en":
        try:
            english_message = translate_text(user_message, detected_lang, "en")
        except Exception:
            english_message = user_message

    # 3. Resilient Multi-Provider AI Inference
    ai_res = ai_router.complete(english_message)
    ai_raw = ai_res.get("text", "")
    provider_used = ai_res.get("provider", "Unknown")

    # 4. Translation back to user language
    final_response = ai_raw
    if detected_lang != "en":
        try:
            final_response = translate_text(ai_raw, "en", detected_lang)
        except Exception:
            final_response = ai_raw

    end_time = time.time()
    response_time_ms = round((end_time - start_time) * 1000, 2)

    # Save to SQLite MessageLog
    try:
        log_entry = MessageLog(
            user_message=user_message,
            detected_language=detected_lang,
            response_time_ms=response_time_ms
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        db.rollback()

    return {
        "response": final_response,
        "detected_language": detected_lang,
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


# ─── Full-Duplex Voice WebSocket (from Voicera) ──────────────────────────────

# ─── Full-Duplex Voice WebSocket (from Voicera) ──────────────────────────────

async def stream_pcm_to_websocket(websocket: WebSocket, pcm_bytes: bytes, chunk_size: int = 1280):
    """Streams 16kHz 16-bit linear PCM audio in subchunks (40ms each) for smooth WebAudio scheduling."""
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
            # ~20ms sleep per 40ms audio chunk provides seamless buffer replenishment
            await asyncio.sleep(0.02)
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
    - Receives continuous 16kHz PCM chunks from browser
    - Energy-based VAD detects speech utterance
    - STT via Groq Whisper Turbo
    - Multi-LLM reasoning via Resilient Router
    - TTS audio streaming via Sarvam AI (bulbul:v3)
    - Real-time barge-in interruption support ('clear' event)
    """
    await websocket.accept()
    vad = VADIterator(threshold=0.028, sampling_rate=SAMPLE_RATE, min_silence_duration_ms=380)
    speech_buffer = []
    is_speaking = False
    is_agent_speaking = False
    agent_speaking_until = 0.0
    turn_count = 0
    full_transcript = []
    call_start_time = time.time()
    greeting_dispatched = False

    await websocket.send_text(json.dumps({
        "event": "connected",
        "message": "OmniVoice Engine Ready (16kHz PCM Stream)"
    }))

    async def send_greeting():
        nonlocal greeting_dispatched, is_agent_speaking, agent_speaking_until
        if greeting_dispatched:
            return
        greeting_dispatched = True
        is_agent_speaking = True
        greeting_text = "Hello! OmniAgent receptionist here. How can I assist you today?"
        full_transcript.append(f"Assistant: {greeting_text}")
        try:
            await websocket.send_text(json.dumps({
                "event": "transcript",
                "role": "assistant",
                "text": greeting_text
            }))
            greeting_pcm = get_preloaded_greeting_pcm()
            if not greeting_pcm:
                greeting_pcm = await generate_sarvam_tts_pcm(greeting_text)
            if greeting_pcm:
                greeting_duration = len(greeting_pcm) / 32000.0
                agent_speaking_until = time.time() + greeting_duration + 0.4
                await stream_pcm_to_websocket(websocket, greeting_pcm)
        except Exception as e:
            print(f"[Greeting Error] {e}")
        finally:
            is_agent_speaking = False

    try:
        while True:
            message_text = await websocket.receive_text()
            data = json.loads(message_text)
            event_type = data.get("event")

            if event_type == "start" or (event_type == "connected" and not greeting_dispatched):
                asyncio.create_task(send_greeting())

            elif event_type == "media":
                payload_b64 = data.get("media", {}).get("payload", "")
                if not payload_b64:
                    continue
                raw_bytes = base64.b64decode(payload_b64)
                chunk_pcm16 = np.frombuffer(raw_bytes, dtype=np.int16)
                chunk_float32 = chunk_pcm16.astype(np.float32) / 32768.0

                # ─── Echo & Speaker Bleed Suppression ────────────────────────
                # While the assistant's voice is playing through speakers, ignore low-to-medium ambient echo
                if time.time() < agent_speaking_until:
                    rms = np.sqrt(np.mean(chunk_float32 ** 2)) if len(chunk_float32) > 0 else 0.0
                    if rms < 0.065:
                        # Speaker feedback / ambient echo — suppress
                        continue
                    else:
                        # Loud intentional user barge-in detected
                        agent_speaking_until = 0.0
                        is_agent_speaking = False
                        speech_buffer.clear()
                        await websocket.send_text(json.dumps({"event": "clear"}))

                vad_event = vad(chunk_float32)

                if vad_event and "start" in vad_event:
                    is_speaking = True
                    speech_buffer.clear()
                    speech_buffer.append(chunk_float32)

                    # BARGE-IN INTERRUPTION: If bot was speaking, immediately tell client to clear audio queue
                    if is_agent_speaking or time.time() < agent_speaking_until:
                        is_agent_speaking = False
                        agent_speaking_until = 0.0
                        await websocket.send_text(json.dumps({"event": "clear"}))

                elif is_speaking:
                    speech_buffer.append(chunk_float32)

                if vad_event and "end" in vad_event and is_speaking:
                    is_speaking = False
                    if not speech_buffer:
                        continue
                    full_audio = np.concatenate(speech_buffer)
                    speech_buffer.clear()

                    # Filter out short clicks, breathing, fan noise, and non-speech audio
                    if not is_valid_speech_audio(full_audio, SAMPLE_RATE, min_duration=0.55, min_rms=0.022):
                        continue

                    wav_bytes = float32_to_wav_bytes(full_audio, SAMPLE_RATE)

                    # 1. Fast Whisper STT with Hallucination Suppression
                    stt_text = transcribe_audio_groq(wav_bytes)
                    if not stt_text or not stt_text.strip():
                        continue

                    turn_count += 1
                    full_transcript.append(f"User: {stt_text}")

                    # Notify client of user transcription
                    await websocket.send_text(json.dumps({
                        "event": "transcript",
                        "role": "user",
                        "text": stt_text
                    }))

                    # 2. Resilient AI Router Generation
                    is_agent_speaking = True
                    ai_prompt = (
                        "You are OmniAgent X, an intelligent multimodal assistant. "
                        "Keep your response concise, polite, natural, and helpful for a spoken voice conversation (1 to 2 sentences max). "
                        f"User said: {stt_text}"
                    )
                    ai_res = ai_router.complete(ai_prompt)
                    bot_text = ai_res.get("text", "I heard you, how can I help you further?")
                    full_transcript.append(f"Assistant: {bot_text}")

                    # Notify client of assistant response
                    await websocket.send_text(json.dumps({
                        "event": "transcript",
                        "role": "assistant",
                        "text": bot_text,
                        "provider": ai_res.get("provider")
                    }))

                    # 3. Text to Speech via Sarvam bulbul:v3
                    tts_pcm = await generate_sarvam_tts_pcm(bot_text)
                    if tts_pcm:
                        tts_dur = len(tts_pcm) / 32000.0
                        agent_speaking_until = time.time() + tts_dur + 0.4
                        await stream_pcm_to_websocket(websocket, tts_pcm)
                    else:
                        # Fallback to Web Speech API signal if server TTS fails
                        await websocket.send_text(json.dumps({
                            "event": "speak_client",
                            "text": bot_text
                        }))

                    is_agent_speaking = False

            elif event_type == "stop":
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket Error] {e}")
    finally:
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

                # Extract Lead if potential customer details exist
                lead_entry = LeadRecord(
                    caller_name="Voice Caller",
                    contact="Web Audio",
                    category="Voice Consultation",
                    summary=transcript_str[:300],
                    source="Voice Agent"
                )
                db.add(lead_entry)
                db.commit()
            except Exception:
                db.rollback()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
