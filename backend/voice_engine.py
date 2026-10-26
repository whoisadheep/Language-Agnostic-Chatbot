import io
import os
import json
import base64
import time
import wave
import asyncio
import numpy as np
import httpx
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv(override=True)

import re

SAMPLE_RATE = 16000

# Common Whisper hallucinations triggered by silence, breaths, or ambient room hum
WHISPER_HALLUCINATIONS = {
    ".", "..", "...", "?", "!", "-", "--", "thank you.", "thank you",
    "thanks for watching.", "thanks for watching", "thank you for watching.",
    "thank you for watching", "subscribe", "subscribe.", "please subscribe.",
    "bye.", "bye", "bye bye.", "bye bye", "you.", "you", "mbc", "mbc.",
    "silence", "[silence]", "(silence)", "[music]", "(music)", "[applause]",
    "so.", "so", "okay.", "okay", "ok.", "ok", "yeah.", "yeah", "hmm.", "hmm",
    "uh.", "uh", "um.", "um", "subtitles by", "subtitled by", "amara.org",
    "thank you very much", "watching", "see you next time",
    "natural human speech", "natural human speech.", "clear conversational voice dialogue."
}

# Supported Sarvam bulbul:v3 language codes
SARVAM_LANG_MAP = {
    "hi": "hi-IN",
    "en": "en-IN",
    "bn": "bn-IN",
    "gu": "gu-IN",
    "kn": "kn-IN",
    "ml": "ml-IN",
    "mr": "mr-IN",
    "or": "or-IN",
    "pa": "pa-IN",
    "ta": "ta-IN",
    "te": "te-IN"
}

ENGLISH_COMMON_WORDS = {
    'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
    'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
    'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she',
    'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their', 'what',
    'so', 'up', 'out', 'if', 'about', 'who', 'get', 'which', 'go', 'me',
    'when', 'make', 'can', 'like', 'time', 'no', 'just', 'him', 'know', 'take',
    'people', 'into', 'year', 'your', 'good', 'some', 'could', 'them', 'see', 'other',
    'than', 'then', 'now', 'look', 'only', 'come', 'its', 'over', 'think', 'also',
    'back', 'after', 'use', 'two', 'how', 'our', 'work', 'first', 'well', 'way',
    'even', 'new', 'want', 'because', 'any', 'these', 'give', 'day', 'most', 'us',
    'hello', 'hi', 'hey', 'morning', 'evening', 'night', 'thanks', 'thank', 'bye',
    'goodbye', 'please', 'help', 'yes', 'ok', 'okay', 'today', 'doing', 'doing?',
    'fine', 'am', 'is', 'are', 'was', 'were', 'tell', 'about', 'yourself'
}

HINGLISH_WORDS = {
    'kya', 'hai', 'hain', 'kaise', 'kaisa', 'kaisi', 'haal', 'aap', 'tum', 'main',
    'hum', 'kar', 'karo', 'rahe', 'raha', 'rahi', 'ho', 'hoon', 'tha', 'thi', 'the',
    'theek', 'namaste', 'namashkar', 'dhanyawad', 'shukriya', 'kaha', 'kidhar', 'kab',
    'kyun', 'batao', 'boliye', 'madad', 'chahiye', 'kaam', 'achha', 'achhi', 'achhe'
}

ROMAJI_WORDS = {
    'arigato', 'arigatou', 'gozaimasu', 'gozaimas', 'konnichiwa', 'sayonara',
    'ohayo', 'ohayou', 'watashi', 'boku', 'kimi', 'namae', 'namaewa',
    'daisuki', 'sumimasen', 'gomen', 'gomenasai', 'hai', 'iie', 'sugoi',
    'kawaii', 'senpai', 'sensei', 'desu'
}

def detect_language(text: str) -> str:
    """
    High-accuracy language detection combining script heuristics, token-level
    lexical matching, and langdetect Bayesian scoring to prevent false positives
    (such as English greetings being misidentified as Somali, Swahili, or Finnish).
    """
    if not text or not text.strip():
        return "en"

    cleaned = text.strip()

    # 1. Non-Latin Unicode script checks (100% deterministic)
    if any('\u0900' <= ch <= '\u097F' for ch in cleaned):
        return "hi"
    if any('\u0980' <= ch <= '\u09FF' for ch in cleaned):
        return "bn"
    if any('\u0600' <= ch <= '\u06FF' or '\u0750' <= ch <= '\u077F' or '\u08A0' <= ch <= '\u08FF' for ch in cleaned):
        return "ar"
    if any('\u3040' <= ch <= '\u309F' or '\u30A0' <= ch <= '\u30FF' for ch in cleaned):
        return "ja"
    if any('\u4E00' <= ch <= '\u9FFF' for ch in cleaned):
        return "zh-cn"
    if any('\u0400' <= ch <= '\u04FF' for ch in cleaned):
        return "ru"
    if any('\u0B80' <= ch <= '\u0BFF' for ch in cleaned):
        return "ta"
    if any('\u0C00' <= ch <= '\u0C7F' for ch in cleaned):
        return "te"

    # 2. Latin token extraction
    tokens = re.findall(r'[a-zA-Z]+', cleaned.lower())
    if not tokens:
        return "en"

    # Hinglish / Romanized Hindi check
    hinglish_matches = sum(1 for t in tokens if t in HINGLISH_WORDS)
    if hinglish_matches >= 2 or (len(tokens) <= 3 and hinglish_matches >= 1 and not all(t in ENGLISH_COMMON_WORDS for t in tokens)):
        return "hi"

    # Romaji / Romanized Japanese check
    romaji_matches = sum(1 for t in tokens if t in ROMAJI_WORDS)
    if romaji_matches >= 1 and not all(t in ENGLISH_COMMON_WORDS for t in tokens if t != 'no'):
        return "ja"

    # Common greetings and conversational phrases in supported languages
    lower_phrase = cleaned.lower().strip("!?,. \t\r\n")
    if lower_phrase in {
        'hola', 'buenos dias', 'buenas tardes', 'buenas noches', 'como estas',
        'como esta', 'muchas gracias', 'por favor', 'que tal', 'amigo'
    }:
        return "es"
    if lower_phrase in {
        'bonjour', 'salut', 'comment ca va', 'comment allez-vous', 'merci',
        'merci beaucoup', 'au revoir', 'sil vous plait', "s'il vous plaît"
    }:
        return "fr"
    if lower_phrase in {
        'hallo', 'guten tag', 'guten morgen', 'guten abend', 'wie gehts',
        'wie geht es dir', 'danke', 'danke schon', 'tschuss', 'auf wiedersehen'
    }:
        return "de"

    # Common English words count
    eng_matches = sum(1 for t in tokens if t in ENGLISH_COMMON_WORDS)
    if len(tokens) <= 3 and eng_matches >= 1:
        return "en"
    if eng_matches / len(tokens) >= 0.45:
        return "en"

    # 3. Meta FastText Sub-Millisecond Classification (176 languages)
    try:
        from fasttext_detector import detect_language_fasttext
        ft_lang, ft_conf = detect_language_fasttext(cleaned)
        if ft_conf >= 0.50:
            return ft_lang
    except Exception:
        pass

    # 4. Fallback to langdetect if FastText unavailable
    try:
        import langdetect
        langdetect.DetectorFactory.seed = 0
        candidates = langdetect.detect_langs(cleaned)
        if not candidates:
            return "en"

        top = candidates[0]
        obscure_codes = {'so', 'sw', 'cy', 'af', 'et', 'lv', 'lt', 'sk', 'sl', 'hr', 'tl', 'id', 'sq', 'nl', 'fi', 'no'}
        if top.lang in obscure_codes:
            for c in candidates:
                if c.lang == "en":
                    return "en"
            if eng_matches > 0:
                return "en"
        return top.lang
    except Exception:
        return "en"

class VADIterator:
    """Ultra-fast, zero-overhead Voice Activity Detector with numpy vectorization."""
    def __init__(self, threshold=0.014, sampling_rate=16000, min_silence_duration_ms=450, speech_pad_ms=60):
        self.threshold = threshold
        self.sampling_rate = sampling_rate
        self.min_silence_samples = sampling_rate * min_silence_duration_ms / 1000
        self.speech_pad_samples = sampling_rate * speech_pad_ms / 1000
        self.reset_states()

    def reset_states(self):
        self.triggered = False
        self.temp_end = 0
        self.current_sample = 0

    def __call__(self, chunk: np.ndarray):
        if not isinstance(chunk, np.ndarray):
            chunk = np.array(chunk, dtype=np.float32)

        window_size = len(chunk)
        self.current_sample += window_size

        if len(chunk) == 0:
            return None

        rms = float(np.sqrt(np.mean(chunk ** 2)))

        if rms >= self.threshold and self.temp_end != 0:
            self.temp_end = 0

        if rms >= self.threshold and not self.triggered:
            self.triggered = True
            return {"start": self.current_sample - self.speech_pad_samples}

        if rms < self.threshold and self.triggered:
            if self.temp_end == 0:
                self.temp_end = self.current_sample
            if self.current_sample - self.temp_end >= self.min_silence_samples:
                self.triggered = False
                self.temp_end = 0
                return {"end": self.current_sample}

        return None

AdaptiveVAD = VADIterator

def is_valid_speech_audio(audio: np.ndarray, sample_rate: int = 16000, min_duration: float = 0.25, min_rms: float = 0.008, min_peak: float = 0.020) -> bool:
    """Verifies that an audio snippet has genuine speech duration, peak volume, and energy."""
    if len(audio) == 0:
        return False
    duration_s = len(audio) / sample_rate
    if duration_s < min_duration:
        return False
    peak = float(np.max(np.abs(audio)))
    if peak < min_peak:
        return False
    rms = float(np.sqrt(np.mean(audio ** 2)))
    if rms < min_rms:
        return False
    return True

def float32_to_wav_bytes(audio: np.ndarray, sample_rate: int = 16000) -> bytes:
    """Convert float32 or int16 numpy audio into WAV container bytes for STT."""
    if audio.dtype == np.float32 or audio.dtype == np.float64:
        pcm16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    else:
        pcm16 = audio.astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm16.tobytes())
    buf.seek(0)
    return buf.read()

def extract_raw_pcm_from_wav(wav_bytes: bytes) -> bytes:
    """Extract raw 16-bit linear PCM from WAV bytes."""
    try:
        with wave.open(io.BytesIO(wav_bytes), 'rb') as w:
            return w.readframes(w.getnframes())
    except Exception as e:
        if wav_bytes.startswith(b'RIFF') and len(wav_bytes) > 44:
            return wav_bytes[44:]
        return wav_bytes

_cached_sarvam_client = None
_cached_async_sarvam_client = None
_tts_http_client: Optional[httpx.AsyncClient] = None

def get_sarvam_client():
    global _cached_sarvam_client
    if _cached_sarvam_client is None:
        api_key = os.getenv("SARVAM_API_KEY")
        if api_key:
            from sarvamai import SarvamAI
            _cached_sarvam_client = SarvamAI(api_subscription_key=api_key)
    return _cached_sarvam_client

def get_async_sarvam_client():
    global _cached_async_sarvam_client
    if _cached_async_sarvam_client is None:
        api_key = os.getenv("SARVAM_API_KEY")
        if api_key:
            from sarvamai import AsyncSarvamAI
            _cached_async_sarvam_client = AsyncSarvamAI(api_subscription_key=api_key)
    return _cached_async_sarvam_client

def get_tts_http_client() -> httpx.AsyncClient:
    global _tts_http_client
    if _tts_http_client is None or _tts_http_client.is_closed:
        _tts_http_client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=120)
        )
    return _tts_http_client

async def warmup_voice_engine():
    """Pre-warms TLS connections to Sarvam API and loads Meta FastText model in background to eliminate cold-start latency."""
    try:
        from fasttext_detector import get_fasttext_model
        await asyncio.to_thread(get_fasttext_model)
    except Exception:
        pass
    try:
        client = get_tts_http_client()
        await client.get("https://api.sarvam.ai", timeout=3.0)
    except Exception:
        pass

async def transcribe_audio_sarvam(wav_bytes: bytes) -> str:
    """
    Asynchronously transcribes audio using Sarvam AI Saaras:v3 model.
    Naturally suppresses silence and background noise hallucinations, returning
    an empty string when no genuine human speech is uttered.
    """
    client = get_async_sarvam_client()
    if not client:
        return await asyncio.to_thread(transcribe_audio_groq, wav_bytes)

    try:
        res = await client.speech_to_text.transcribe(
            file=("speech.wav", wav_bytes, "audio/wav"),
            model="saaras:v3",
            language_code="unknown"
        )
        raw_text = (getattr(res, "transcript", "") or "").strip()
        if not raw_text:
            print("[Sarvam STT returned empty. Falling back to Groq Whisper...]")
            return await asyncio.to_thread(transcribe_audio_groq, wav_bytes)

        # Filter out punctuation-only strings (e.g. '.', '...', '?', '!')
        alnum_chars = re.sub(r"[^\w\u0900-\u097F]", "", raw_text)
        if len(alnum_chars) < 2:
            print("[Sarvam STT punctuation only. Falling back to Groq Whisper...]")
            return await asyncio.to_thread(transcribe_audio_groq, wav_bytes)

        return raw_text
    except Exception as e:
        print(f"[Sarvam STT Warning] {e}. Falling back to Groq Whisper.")
        return await asyncio.to_thread(transcribe_audio_groq, wav_bytes)

_cached_groq_client = None

def get_groq_client():
    global _cached_groq_client
    if _cached_groq_client is None:
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            from groq import Groq
            _cached_groq_client = Groq(api_key=groq_key)
    return _cached_groq_client

def transcribe_audio_groq(wav_bytes: bytes) -> str:
    """Transcribe speech WAV bytes using Groq Whisper as fallback with hallucination suppression."""
    client = get_groq_client()
    if not client:
        return ""
    try:
        resp = client.audio.transcriptions.create(
            file=("speech.wav", wav_bytes),
            model="whisper-large-v3-turbo",
            response_format="json",
            temperature=0.0
        )
        raw_text = resp.text.strip()
        if not raw_text:
            return ""

        # Filter out punctuation-only strings (e.g. '.', '...', '?', '!')
        alnum_chars = re.sub(r"[^\w\u0900-\u097F]", "", raw_text)
        if len(alnum_chars) < 2:
            return ""

        # Filter out known Whisper silence hallucinations
        if raw_text.lower().strip("!?,. ") in WHISPER_HALLUCINATIONS:
            return ""

        return raw_text
    except Exception as e:
        print(f"[STT Error] Groq whisper transcription failed: {e}")
        return ""

async def generate_sarvam_tts_pcm(text: str, language_code: Optional[str] = None, speaker: str = "kavya") -> Optional[bytes]:
    """Generate raw 16kHz linear PCM audio bytes using Sarvam AI TTS (bulbul:v3) with persistent keep-alive."""
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        return None

    # Resolve target language code for Sarvam
    resolved_lang = "en-IN"
    if language_code:
        norm = language_code.lower().split("-")[0]
        if norm in SARVAM_LANG_MAP:
            resolved_lang = SARVAM_LANG_MAP[norm]
        elif language_code in SARVAM_LANG_MAP.values():
            resolved_lang = language_code
        else:
            # Language not supported by Sarvam (e.g. Spanish, French, German) -> fallback to client WebSpeech
            return None
    else:
        # Auto-detect language code if not provided
        detected = detect_language(text)
        if detected in SARVAM_LANG_MAP:
            resolved_lang = SARVAM_LANG_MAP[detected]
        else:
            return None

    url = "https://api.sarvam.ai/text-to-speech"
    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": [text[:500]],
        "target_language_code": resolved_lang,
        "speaker": speaker,
        "pitch": 0,
        "pace": 1.0,
        "loudness": 1.5,
        "speech_sample_rate": 16000,
        "enable_preprocessing": True,
        "model": "bulbul:v3"
    }
    try:
        client = get_tts_http_client()
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            audios = data.get("audios", [])
            if audios:
                wav_data = base64.b64decode(audios[0])
                # Extract raw PCM16 bytes from the WAV container
                return extract_raw_pcm_from_wav(wav_data)
        else:
            print(f"[TTS Error] Sarvam returned {resp.status_code}: {resp.text[:150]}")
    except Exception as e:
        print(f"[TTS Error] Sarvam TTS REST request failed: {e}")
    return None

def get_preloaded_greeting_pcm() -> Optional[bytes]:
    """Loads pre-recorded OmniAgent greeting PCM if present."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "assets", "greeting.pcm"),
        os.path.join(base_dir, "greeting.pcm")
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    return f.read()
            except Exception:
                pass
    return None
