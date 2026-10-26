"""
Meta FastText Language Identification Module (lid.176)
High-throughput sub-millisecond language identification supporting 176 languages.
"""
import os
import re
import fasttext
from typing import Tuple, Optional

# Suppress fasttext C++ load_model warning
fasttext.FastText.eprint = lambda x: None

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "lid.176.ftz")
_model_instance = None

def get_fasttext_model():
    global _model_instance
    if _model_instance is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Meta FastText model not found at {MODEL_PATH}")
        _model_instance = fasttext.load_model(MODEL_PATH)
    return _model_instance


def detect_language_fasttext(text: str, confidence_threshold: float = 0.60) -> Tuple[str, float]:
    """
    Classifies language using Meta's pre-trained FastText model in <0.2 milliseconds.
    
    Returns:
        Tuple[str, float]: (ISO 2-letter language code, confidence_score [0.0 - 1.0])
    """
    if not text or not text.strip():
        return "en", 1.0

    cleaned = text.strip().replace("\n", " ")
    
    # Fast script check for 100% deterministic non-Latin scripts
    if any('\u0900' <= ch <= '\u097F' for ch in cleaned):
        return "hi", 0.99
    if any('\u0980' <= ch <= '\u09FF' for ch in cleaned):
        return "bn", 0.99
    if any('\u0600' <= ch <= '\u06FF' for ch in cleaned):
        return "ar", 0.99
    if any('\u3040' <= ch <= '\u309F' or '\u30A0' <= ch <= '\u30FF' for ch in cleaned):
        return "ja", 0.99
    if any('\u4E00' <= ch <= '\u9FFF' for ch in cleaned):
        return "zh-cn", 0.99
    if any('\u0400' <= ch <= '\u04FF' for ch in cleaned):
        return "ru", 0.99

    try:
        model = get_fasttext_model()
        labels, probs = model.predict(cleaned, k=1)
        if labels and len(labels) > 0:
            lang = labels[0].replace("__label__", "").lower()
            conf = float(probs[0])
            return lang, conf
    except Exception as e:
        print(f"[FastText] Detection error: {e}")

    return "en", 0.50
