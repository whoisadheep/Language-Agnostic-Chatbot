"""
Test translation quality using LibreTranslate.
These tests hit the live LibreTranslate public endpoint.
Marked as 'integration' — they are skipped automatically if the API is unreachable.
"""
import pytest
import requests

LIBRETRANSLATE_URL = "https://libretranslate.com/translate"


def _api_available():
    """Check if LibreTranslate API is reachable and accepting requests."""
    try:
        payload = {"q": "hello", "source": "en", "target": "es", "format": "text"}
        resp = requests.post(LIBRETRANSLATE_URL, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


# Skip the entire module if the API is down or rate-limited
pytestmark = pytest.mark.skipif(
    not _api_available(),
    reason="LibreTranslate API is unavailable or rate-limited"
)


def _translate(text: str, source: str, target: str) -> str:
    """Helper to call LibreTranslate API."""
    payload = {
        "q": text,
        "source": source,
        "target": target,
        "format": "text",
    }
    resp = requests.post(LIBRETRANSLATE_URL, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json().get("translatedText", "")


# ── Tests ───────────────────────────────────────────────────────────────────────

class TestTranslation:
    """Suite for validating translation round-trip quality."""

    @pytest.mark.integration
    def test_spanish_to_english(self):
        """Spanish → English should produce a sensible English result."""
        result = _translate("Hola, ¿cómo estás?", "es", "en")
        assert result, "Translation returned empty"
        result_lower = result.lower()
        assert any(word in result_lower for word in ["hello", "hi", "how", "are"]), (
            f"Translation doesn't look like English: '{result}'"
        )

    @pytest.mark.integration
    def test_french_to_english(self):
        """French → English should produce a sensible English result."""
        result = _translate("Bonjour, comment allez-vous?", "fr", "en")
        assert result, "Translation returned empty"
        result_lower = result.lower()
        assert any(word in result_lower for word in ["hello", "how", "good"]), (
            f"Translation doesn't look like English: '{result}'"
        )

    @pytest.mark.integration
    def test_english_to_hindi(self):
        """English → Hindi should return Devanagari script characters."""
        result = _translate("Hello, how are you?", "en", "hi")
        assert result, "Translation returned empty"
        has_devanagari = any("\u0900" <= ch <= "\u097F" for ch in result)
        assert has_devanagari, f"Expected Devanagari script, got: '{result}'"

    @pytest.mark.integration
    def test_roundtrip_preserves_meaning(self):
        """English → Spanish → English should roughly preserve meaning."""
        original = "The weather is very nice today"
        spanish = _translate(original, "en", "es")
        assert spanish, "First translation returned empty"

        back_to_english = _translate(spanish, "es", "en")
        assert back_to_english, "Roundtrip translation returned empty"

        back_lower = back_to_english.lower()
        assert any(word in back_lower for word in ["weather", "nice", "today", "good", "time"]), (
            f"Roundtrip lost meaning. Original: '{original}' → '{back_to_english}'"
        )

    @pytest.mark.integration
    def test_translation_api_returns_json(self):
        """The API should always return valid JSON with translatedText key."""
        payload = {"q": "test", "source": "en", "target": "es", "format": "text"}
        resp = requests.post(LIBRETRANSLATE_URL, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        assert "translatedText" in data, f"Missing 'translatedText' key: {data}"
