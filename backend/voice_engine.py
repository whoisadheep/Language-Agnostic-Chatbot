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
    "uh.", "uh", "um.", "um", "subtitles by", "subtitled by"
}

class VADIterator:
    """Lightweight Energy/RMS-based Voice Activity Detector with noise floor suppression."""
    def __init__(self, threshold=0.028, sampling_rate=16000, min_silence_duration_ms=380, speech_pad_ms=40):
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

        rms = np.sqrt(np.mean(chunk ** 2)) if len(chunk) > 0 else 0.0

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

def is_valid_speech_audio(audio: np.ndarray, sample_rate: int = 16000, min_duration: float = 0.55, min_rms: float = 0.022) -> bool:
    """Verifies that an audio snippet has sufficient duration and energy to be genuine human speech."""
    if len(audio) == 0:
        return False
    duration_s = len(audio) / sample_rate
    if duration_s < min_duration:
        return False
    rms = np.sqrt(np.mean(audio ** 2))
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

def transcribe_audio_groq(wav_bytes: bytes) -> str:
    """Transcribe speech WAV bytes using Groq Whisper with strict hallucination suppression."""
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        return ""
    from groq import Groq
    client = Groq(api_key=groq_key)
    try:
        resp = client.audio.transcriptions.create(
            file=("speech.wav", wav_bytes),
            model="whisper-large-v3-turbo",
            response_format="json",
            temperature=0.0,
            prompt="Clear conversational voice dialogue. Natural human speech."
        )
        raw_text = resp.text.strip()
        if not raw_text:
            return ""

        # Filter out punctuation-only strings (e.g. '.', '...', '?', '!')
        alnum_chars = re.sub(r"[^\w\u0900-\u097F]", "", raw_text)
        if len(alnum_chars) < 2:
            return ""

        # Filter out known Whisper silence hallucinations
        if raw_text.lower() in WHISPER_HALLUCINATIONS:
            return ""

        return raw_text
    except Exception as e:
        print(f"[STT Error] Groq whisper transcription failed: {e}")
        return ""

async def generate_sarvam_tts_pcm(text: str, language_code: Optional[str] = None, speaker: str = "kavya") -> Optional[bytes]:
    """Generate raw 16kHz linear PCM audio bytes using Sarvam AI TTS (bulbul:v3)."""
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        return None

    # Auto-detect language code if not provided
    if not language_code:
        # Check if text contains Devanagari characters
        if any('\u0900' <= char <= '\u097F' for char in text):
            language_code = "hi-IN"
        else:
            language_code = "en-IN"

    url = "https://api.sarvam.ai/text-to-speech"
    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": [text[:500]],
        "target_language_code": language_code,
        "speaker": speaker,
        "pitch": 0,
        "pace": 1.0,
        "loudness": 1.5,
        "speech_sample_rate": 16000,
        "enable_preprocessing": True,
        "model": "bulbul:v3"
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
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
    """Loads pre-recorded greeting PCM if present."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "assets", "greeting.pcm"),
        os.path.join(base_dir, "greeting.pcm"),
        "/home/whoisadheep/Documents/Voicera/assets/greeting.pcm"
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    return f.read()
            except Exception:
                pass
    return None
