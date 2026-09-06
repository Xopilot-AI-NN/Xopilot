"""
Файл: /App/services/ai.py
Описание: Тестовая локальная ИИ (пункт 5 плана) — классификатор тональности через ONNX
    (Rust: advanced_xopilot.PySentimentClassifier, Services/src/ai/mod.rs).

    Модель НЕ обученная — это проверка пайплайна текст -> ONNX -> ответ, а не качества ответов.
"""

import os
from typing import Optional, Tuple

try:
    import advanced_xopilot  # type: ignore

    _IMPORT_ERROR: Optional[Exception] = None
except Exception as exc:  # noqa: BLE001 — модуль может быть ещё не собран
    advanced_xopilot = None  # type: ignore
    _IMPORT_ERROR = exc

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "models", "sentiment.onnx")

_classifier = None  # единый экземпляр на процесс приложения — загрузка ONNX-модели не бесплатная


def _get_classifier():
    global _classifier
    if _classifier is None:
        if advanced_xopilot is None:
            raise RuntimeError(
                "advanced_xopilot не собран — выполните `maturin develop` в Services/"
            ) from _IMPORT_ERROR
        _classifier = advanced_xopilot.PySentimentClassifier(_MODEL_PATH)
    return _classifier


def classify_sentiment(text: str) -> Optional[Tuple[str, float]]:
    """(метка, уверенность) или None, если модель недоступна — вызывающий код должен это обработать."""
    try:
        label, score = _get_classifier().classify(text)
        return label, score
    except Exception:
        return None


_REPLIES = {
    "negative": "Понимаю, звучит не очень. Чем могу помочь?",
    "neutral": "Принято. Продолжаем?",
    "positive": "Здорово! Рад, что всё идёт хорошо.",
}


def reply_for_sentiment(label: str) -> str:
    return _REPLIES.get(label, _REPLIES["neutral"])