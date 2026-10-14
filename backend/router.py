import time
import os
import requests
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv(override=True)

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
            "groq": ProviderCircuitBreaker("Groq (LLaMA 3.3 70B)", failure_threshold=3, cooldown_seconds=20.0),
            "gemini": ProviderCircuitBreaker("Google Gemini 2.5 Flash", failure_threshold=3, cooldown_seconds=30.0),
            "openrouter": ProviderCircuitBreaker("OpenRouter Failover", failure_threshold=3, cooldown_seconds=30.0),
        }

    def _call_groq(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            raise ValueError("GROQ_API_KEY not configured")
        from groq import Groq
        client = Groq(api_key=groq_key)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
            timeout=15.0
        )
        return completion.choices[0].message.content.strip()

    def _call_gemini(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key or gemini_key.startswith("sk-"):
            raise ValueError("Valid GEMINI_API_KEY not configured")
        from google import genai
        client = genai.Client(api_key=gemini_key)

        full_prompt = f"System: {system_prompt}\n\nUser: {prompt}" if system_prompt else prompt
        
        # Try available models in order
        for model in ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=full_prompt,
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                continue
        raise RuntimeError("All Gemini models failed to generate response")

    def _call_openrouter(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEYS")
        if not key:
            # Check if gemini key is an openrouter key
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
        messages.append({"role": "user", "content": prompt})

        model = os.getenv("OPENROUTER_MODEL", "openrouter/free")
        data = {
            "model": model,
            "messages": messages,
            "max_tokens": 1024
        }
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=25)
        if resp.status_code == 200:
            res_json = resp.json()
            choices = res_json.get("choices", [])
            if choices and "message" in choices[0]:
                return choices[0]["message"]["content"].strip()
        raise RuntimeError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:200]}")

    def complete(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Dispatches prompt across providers in priority order:
        1. Groq (Ultra-low latency sub-300ms)
        2. Google Gemini (Deep multimodal reasoning)
        3. OpenRouter (Multi-model free/backup tier)
        With automatic circuit breaker protection.
        """
        load_dotenv(override=True)
        providers = [
            ("groq", "Groq LLaMA 3.3", self._call_groq),
            ("gemini", "Gemini 2.5 Flash", self._call_gemini),
            ("openrouter", "OpenRouter Backup", self._call_openrouter),
        ]

        errors = []
        for provider_id, display_name, call_fn in providers:
            breaker = self.breakers[provider_id]
            if not breaker.can_request():
                continue

            start_time = time.time()
            try:
                reply = call_fn(prompt, system_prompt)
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

        # If all providers failed or were open
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
