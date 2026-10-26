import pytest
from fasttext_detector import detect_language_fasttext, get_fasttext_model

def test_fasttext_model_loads():
    model = get_fasttext_model()
    assert model is not None

@pytest.mark.parametrize("text,expected_lang", [
    ("Hello, how are you doing today?", "en"),
    ("Good morning everyone, let us begin.", "en"),
    ("Bonjour tout le monde, comment allez-vous?", "fr"),
    ("Hola amigo, ¿cómo estás?", "es"),
    ("Guten Tag, wie geht es Ihnen heute?", "de"),
    ("Привет, как ваши дела?", "ru"),
    ("नमस्ते, आप कैसे हैं?", "hi"),
    ("こんにちは、元気ですか？", "ja"),
    ("আপনি কেমন আছেন?", "bn"),
    ("مرحبا، كيف حالك اليوم؟", "ar"),
])
def test_fasttext_language_accuracy(text, expected_lang):
    lang, conf = detect_language_fasttext(text)
    assert lang == expected_lang
    assert conf >= 0.50
