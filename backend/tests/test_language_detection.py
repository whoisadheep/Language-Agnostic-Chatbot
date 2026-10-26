"""
Test language detection accuracy using langdetect.
Validates that sample sentences in Hindi, French, Spanish, Arabic, and Japanese
are correctly identified.
"""
import pytest
import langdetect
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from voice_engine import detect_language


# ── Fixtures ────────────────────────────────────────────────────────────────────

DETECTION_CASES = [
    # (sample_text, expected_lang_code, language_name)
    ("नमस्ते, आप कैसे हैं?", "hi", "Hindi"),
    ("मुझे हिंदी में बात करना पसंद है", "hi", "Hindi"),
    ("Bonjour, comment allez-vous aujourd'hui?", "fr", "French"),
    ("Je suis très content de vous rencontrer", "fr", "French"),
    ("Hola, ¿cómo estás? Me llamo Carlos.", "es", "Spanish"),
    ("Buenos días, espero que tengas un buen día", "es", "Spanish"),
    ("مرحبا، كيف حالك اليوم؟", "ar", "Arabic"),
    ("أنا سعيد جداً بلقائك", "ar", "Arabic"),
    ("こんにちは、元気ですか？", "ja", "Japanese"),
    ("今日はとても良い天気ですね", "ja", "Japanese"),
]


# ── Tests ───────────────────────────────────────────────────────────────────────

class TestLanguageDetection:
    """Suite for validating langdetect accuracy across target languages."""

    @pytest.mark.parametrize("text, expected_lang, lang_name", DETECTION_CASES)
    def test_detects_correct_language(self, text, expected_lang, lang_name):
        """langdetect should return the correct ISO 639-1 code."""
        detected = langdetect.detect(text)
        assert detected == expected_lang, (
            f"Expected '{lang_name}' ({expected_lang}) but got '{detected}' "
            f"for text: \"{text[:40]}...\""
        )

    def test_english_detection(self):
        """English detection should work reliably."""
        texts = [
            "Hello, how are you doing today?",
            "The weather is beautiful this morning.",
            "I would like to order some coffee please.",
        ]
        for text in texts:
            detected = langdetect.detect(text)
            assert detected == "en", f"Expected 'en' but got '{detected}' for: \"{text}\""

    def test_empty_string_raises(self):
        """An empty string should raise LangDetectException."""
        with pytest.raises(langdetect.lang_detect_exception.LangDetectException):
            langdetect.detect("")

    def test_numeric_only_is_unpredictable(self):
        """Pure numeric strings may fail or give unreliable results."""
        # We just verify it doesn't crash; the result is non-deterministic
        try:
            result = langdetect.detect("123456789")
            assert isinstance(result, str)
        except langdetect.lang_detect_exception.LangDetectException:
            pass  # This is also acceptable


class TestDetectLanguageFunction:
    """Suite validating custom robust detect_language function for conversational edge cases."""

    @pytest.mark.parametrize("text, expected_lang", [
        ("Hello, how are you today?", "en"),
        ("hi", "en"),
        ("hello", "en"),
        ("good morning", "en"),
        ("thanks", "en"),
        ("thank you", "en"),
        ("bye", "en"),
        ("Can you help me with this?", "en"),
        ("नमस्ते, आप कैसे हैं?", "hi"),
        ("aap kaise ho", "hi"),
        ("kya haal hai", "hi"),
        ("namaste", "hi"),
        ("Bonjour, comment allez-vous aujourd'hui?", "fr"),
        ("bonjour", "fr"),
        ("salut", "fr"),
        ("Hola, ¿cómo estás? Me llamo Carlos.", "es"),
        ("hola", "es"),
        ("buenos dias", "es"),
        ("مرحبا، كيف حالك اليوم؟", "ar"),
        ("こんにちは、元気ですか？", "ja"),
    ])
    def test_detect_language_accuracy(self, text, expected_lang):
        assert detect_language(text) == expected_lang
