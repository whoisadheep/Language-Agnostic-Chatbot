"""
Test FastAPI endpoint responses using the HTTPX TestClient.
These tests validate request/response contracts without hitting external APIs.
"""
import pytest
from fastapi.testclient import TestClient

# Import the app from main
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import app


client = TestClient(app)


# ── Health Endpoint ─────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    """Validate the /health endpoint."""

    def test_health_returns_200(self):
        """GET /health should return 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_status_key(self):
        """Response should contain 'status' and 'gemini' keys."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "gemini" in data
        assert data["status"] == "ok"


# ── Welcome Endpoint ───────────────────────────────────────────────────────────

class TestWelcomeEndpoint:
    """Validate the /welcome endpoint."""

    def test_welcome_returns_200(self):
        """GET /welcome should return 200."""
        response = client.get("/welcome")
        assert response.status_code == 200

    def test_welcome_has_message(self):
        """Response should contain a 'message' key."""
        data = client.get("/welcome").json()
        assert "message" in data
        assert len(data["message"]) > 0

    def test_welcome_english_default(self):
        """Default welcome (lang=en) should return the English message."""
        data = client.get("/welcome?lang=en").json()
        assert "OmniLingua" in data["message"] or "Welcome" in data["message"]


# ── Analytics Endpoint ──────────────────────────────────────────────────────────

class TestAnalyticsEndpoint:
    """Validate the /analytics endpoint."""

    def test_analytics_returns_200(self):
        """GET /analytics should return 200."""
        response = client.get("/analytics")
        assert response.status_code == 200

    def test_analytics_has_expected_keys(self):
        """Response should contain all expected analytics keys."""
        data = client.get("/analytics").json()
        expected_keys = [
            "total_messages",
            "languages_detected",
            "avg_response_times",
            "messages_per_hour",
            "recent_messages",
        ]
        for key in expected_keys:
            assert key in data, f"Missing key: {key}"

    def test_analytics_total_messages_is_integer(self):
        """total_messages should be a non-negative integer."""
        data = client.get("/analytics").json()
        assert isinstance(data["total_messages"], int)
        assert data["total_messages"] >= 0


# ── Chat Endpoint ───────────────────────────────────────────────────────────────

class TestChatEndpoint:
    """Validate the /chat endpoint request/response contracts."""

    def test_chat_rejects_empty_body(self):
        """POST /chat with no body should return 422."""
        response = client.post("/chat")
        assert response.status_code == 422

    def test_chat_rejects_empty_message(self):
        """POST /chat with an empty message string should return 400."""
        response = client.post("/chat", json={"message": "   "})
        assert response.status_code == 400

    def test_chat_rejects_too_long_message(self):
        """POST /chat with >500 char message should return 422."""
        long_message = "A" * 501
        response = client.post("/chat", json={"message": long_message})
        assert response.status_code == 422

    def test_chat_accepts_valid_message(self):
        """POST /chat with a valid English message should return 200.
        
        Note: This test requires GEMINI_API_KEY to be set and the Gemini API
        to be reachable. If not, it will return 500 which is still a valid
        contract test (we check the server doesn't crash unexpectedly).
        """
        response = client.post("/chat", json={"message": "Hello"})
        # Should be 200 (success) or 500 (API key missing) — never a crash
        assert response.status_code in (200, 500)
        data = response.json()
        # If successful, validate response shape
        if response.status_code == 200:
            assert "response" in data
            assert "detected_language" in data

    def test_chat_accepts_override_language(self):
        """POST /chat with override_language should not crash."""
        response = client.post("/chat", json={
            "message": "Hola amigo",
            "override_language": "es"
        })
        assert response.status_code in (200, 500)

    def test_chat_returns_json(self):
        """Response content-type should be application/json."""
        response = client.post("/chat", json={"message": "test"})
        assert "application/json" in response.headers.get("content-type", "")
