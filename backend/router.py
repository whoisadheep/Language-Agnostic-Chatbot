import time
import os
import asyncio
import httpx
import requests
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path, override=True)

class CircuitState:
    CLOSED = "CLOSED"       # Healthy, accepting requests
    OPEN = "OPEN"           # Failed, cooling down
    HALF_OPEN = "HALF_OPEN" # Testing recovery

class ProviderCircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 3, cooldown_seconds: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.last_failure_time = 0.0
        self.total_requests = 0
        self.successful_requests = 0
        self.latencies: List[float] = []

    def can_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            # Check if cooldown period has elapsed
            if time.time() - self.last_failure_time >= self.cooldown_seconds:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        if self.state == CircuitState.HALF_OPEN:
            return True
        return False

    def record_success(self, latency_ms: float):
        self.consecutive_failures = 0
        self.successful_requests += 1
        self.total_requests += 1
        self.latencies.append(latency_ms)
        if len(self.latencies) > 50:
            self.latencies.pop(0)
        self.state = CircuitState.CLOSED

    def record_failure(self, error: str):
        self.consecutive_failures += 1
        self.total_requests += 1
        self.last_failure_time = time.time()
        if self.consecutive_failures >= self.failure_threshold or self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN

    @property
    def avg_latency_ms(self) -> float:
        if not self.latencies:
            return 0.0
        return round(sum(self.latencies) / len(self.latencies), 1)

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state,
            "consecutive_failures": self.consecutive_failures,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "avg_latency_ms": self.avg_latency_ms,
            "is_available": self.can_request()
        }


class ResilientAIRouter:
    def __init__(self):
        self.breakers = {
            "groq": ProviderCircuitBreaker("Groq LLaMA 3.3", failure_threshold=3, cooldown_seconds=20.0),
            "gemini": ProviderCircuitBreaker("Google Gemini 2.5 Flash", failure_threshold=3, cooldown_seconds=30.0),
            "openrouter": ProviderCircuitBreaker("OpenRouter Failover", failure_threshold=3, cooldown_seconds=30.0),
        }
        self._groq_client = None
        self._groq_async_client = None
        self._cached_groq_key = None
        self._gemini_client = None
        self._cached_gemini_key = None
        self._http_async_client = None

    def _get_groq_client(self):
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            raise ValueError("GROQ_API_KEY not configured")
        if self._groq_client is None or self._cached_groq_key != groq_key:
            from groq import Groq
            self._groq_client = Groq(api_key=groq_key)
            self._cached_groq_key = groq_key
        return self._groq_client

    def _get_groq_async_client(self):
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            raise ValueError("GROQ_API_KEY not configured")
        if self._groq_async_client is None or self._cached_groq_key != groq_key:
            from groq import AsyncGroq
            self._groq_async_client = AsyncGroq(api_key=groq_key)
            self._cached_groq_key = groq_key
        return self._groq_async_client

    def _get_gemini_client(self):
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key or gemini_key.startswith("sk-"):
            raise ValueError("Valid GEMINI_API_KEY not configured")
        if self._gemini_client is None or self._cached_gemini_key != gemini_key:
            from google import genai
            self._gemini_client = genai.Client(api_key=gemini_key)
            self._cached_gemini_key = gemini_key
        return self._gemini_client

    def _get_http_async_client(self) -> httpx.AsyncClient:
        if self._http_async_client is None or self._http_async_client.is_closed:
            self._http_async_client = httpx.AsyncClient(timeout=15.0)
        return self._http_async_client

    def _call_groq(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 512, history: Optional[List[Dict[str, str]]] = None) -> str:
        client = self._get_groq_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            for item in history:
                messages.append({"role": item.get("role", "user"), "content": item.get("content", "")})
        messages.append({"role": "user", "content": prompt})

        model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.6,
            max_tokens=max_tokens,
            timeout=12.0
        )
        return completion.choices[0].message.content.strip()

    async def _call_groq_async(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 512, history: Optional[List[Dict[str, str]]] = None) -> str:
        client = self._get_groq_async_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            for item in history:
                messages.append({"role": item.get("role", "user"), "content": item.get("content", "")})
        messages.append({"role": "user", "content": prompt})

        model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        completion = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.6,
            max_tokens=max_tokens,
            timeout=12.0
        )
        return completion.choices[0].message.content.strip()

    def _call_gemini(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 512, history: Optional[List[Dict[str, str]]] = None) -> str:
        client = self._get_gemini_client()
        parts = []
        if system_prompt:
            parts.append(f"System: {system_prompt}")
        if history:
            for item in history:
                r = "User" if item.get("role") == "user" else "Assistant"
                parts.append(f"{r}: {item.get('content', '')}")
        parts.append(f"User: {prompt}")
        full_prompt = "\n\n".join(parts)
        
        # Try available models in order
        for model in ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=full_prompt,
                )
                if response and response.text:
                    return response.text.strip()
            except Exception:
                continue
        raise RuntimeError("All Gemini models failed to generate response")

    async def _call_gemini_async(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 512, history: Optional[List[Dict[str, str]]] = None) -> str:
        return await asyncio.to_thread(self._call_gemini, prompt, system_prompt, max_tokens, history)

    def _call_openrouter(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 512, history: Optional[List[Dict[str, str]]] = None) -> str:
        key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEYS")
        if not key:
            g_key = os.getenv("GEMINI_API_KEY")
            if g_key and g_key.startswith("sk-"):
                key = g_key
        if not key:
            raise ValueError("OPENROUTER_API_KEY not configured")
            
        if "," in key:
            key = key.split(",")[0].strip()

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "OmniAgent AI"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            for item in history:
                messages.append({"role": item.get("role", "user"), "content": item.get("content", "")})
        messages.append({"role": "user", "content": prompt})

        model = os.getenv("OPENROUTER_MODEL", "openrouter/free")
        data = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens
        }
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=15)
        if resp.status_code == 200:
            res_json = resp.json()
            choices = res_json.get("choices", [])
            if choices and "message" in choices[0]:
                return choices[0]["message"]["content"].strip()
        raise RuntimeError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:200]}")

    async def _call_openrouter_async(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 512, history: Optional[List[Dict[str, str]]] = None) -> str:
        key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEYS")
        if not key:
            g_key = os.getenv("GEMINI_API_KEY")
            if g_key and g_key.startswith("sk-"):
                key = g_key
        if not key:
            raise ValueError("OPENROUTER_API_KEY not configured")
            
        if "," in key:
            key = key.split(",")[0].strip()

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "OmniAgent AI"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            for item in history:
                messages.append({"role": item.get("role", "user"), "content": item.get("content", "")})
        messages.append({"role": "user", "content": prompt})

        model = os.getenv("OPENROUTER_MODEL", "openrouter/free")
        data = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens
        }
        client = self._get_http_async_client()
        resp = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=15)
        if resp.status_code == 200:
            res_json = resp.json()
            choices = res_json.get("choices", [])
            if choices and "message" in choices[0]:
                return choices[0]["message"]["content"].strip()
        raise RuntimeError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:200]}")

    def complete(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 512, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Synchronous provider dispatch with automatic circuit breaker protection:
        1. Groq (Ultra-low latency sub-300ms)
        2. Google Gemini (Deep multimodal reasoning)
        3. OpenRouter (Multi-model backup tier)
        """
        providers = [
            ("groq", "Groq LLaMA 3.3", lambda p, s, m: self._call_groq(p, s, m, history)),
            ("gemini", "Gemini 2.5 Flash", lambda p, s, m: self._call_gemini(p, s, m, history)),
            ("openrouter", "OpenRouter Backup", lambda p, s, m: self._call_openrouter(p, s, m, history)),
        ]

        errors = []
        for provider_id, display_name, call_fn in providers:
            breaker = self.breakers[provider_id]
            if not breaker.can_request():
                continue

            start_time = time.time()
            try:
                reply = call_fn(prompt, system_prompt, max_tokens)
                latency_ms = round((time.time() - start_time) * 1000, 2)
                breaker.record_success(latency_ms)
                return {
                    "text": reply,
                    "provider": display_name,
                    "provider_id": provider_id,
                    "latency_ms": latency_ms,
                    "status": "success"
                }
            except Exception as e:
                latency_ms = round((time.time() - start_time) * 1000, 2)
                breaker.record_failure(str(e))
                errors.append(f"{display_name} failed ({latency_ms}ms): {str(e)[:100]}")
                continue

        fallback_msg = "I am currently processing your request, but all AI providers are under heavy load. Please try again in a few moments."
        return {
            "text": fallback_msg,
            "provider": "Offline Fallback",
            "provider_id": "fallback",
            "latency_ms": 0.0,
            "status": "fallback",
            "errors": errors
        }

    async def complete_async(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 512, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Fully asynchronous, non-blocking AI completion with circuit breaker protection.
        Prioritizes warm connection pools and sub-300ms execution.
        """
        providers = [
            ("groq", "Groq LLaMA 3.3", lambda p, s, m: self._call_groq_async(p, s, m, history)),
            ("gemini", "Gemini 2.5 Flash", lambda p, s, m: self._call_gemini_async(p, s, m, history)),
            ("openrouter", "OpenRouter Backup", lambda p, s, m: self._call_openrouter_async(p, s, m, history)),
        ]

        errors = []
        for provider_id, display_name, call_fn in providers:
            breaker = self.breakers[provider_id]
            if not breaker.can_request():
                continue

            start_time = time.time()
            try:
                reply = await call_fn(prompt, system_prompt, max_tokens)
                latency_ms = round((time.time() - start_time) * 1000, 2)
                breaker.record_success(latency_ms)
                return {
                    "text": reply,
                    "provider": display_name,
                    "provider_id": provider_id,
                    "latency_ms": latency_ms,
                    "status": "success"
                }
            except Exception as e:
                latency_ms = round((time.time() - start_time) * 1000, 2)
                breaker.record_failure(str(e))
                errors.append(f"{display_name} failed ({latency_ms}ms): {str(e)[:100]}")
                continue

        fallback_msg = "I am currently processing your request, but all AI providers are under heavy load. Please try again in a few moments."
        return {
            "text": fallback_msg,
            "provider": "Offline Fallback",
            "provider_id": "fallback",
            "latency_ms": 0.0,
            "status": "fallback",
            "errors": errors
        }

    def get_telemetry(self) -> List[Dict[str, Any]]:
        return [b.get_status() for b in self.breakers.values()]

ai_router = ResilientAIRouter()
