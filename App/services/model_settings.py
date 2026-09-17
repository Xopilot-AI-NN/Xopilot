"""
Файл: App/services/model_settings.py
Описание: Выбор локальных LiteRT-LM моделей для обычного чата и Live.

Настройки сохраняются в локальной БД. Если Rust-БД недоступна во время
разработки, выбор всё равно действует до закрытия приложения.
"""

from __future__ import annotations

from .db import get_setting, set_setting
from .llm import DEFAULT_FILENAME, list_local_models, model_supports_audio


CHAT_MODEL_SETTING_KEY = "chat_model"
LIVE_MODEL_SETTING_KEY = "live_model"

_session_chat_model: str | None = None
_session_live_model: str | None = None

_KNOWN_NAMES = {
    DEFAULT_FILENAME: "Gemma 4 E2B",
}


def model_display_name(filename: str | None) -> str:
    if not filename:
        return "Модель не выбрана"
    if filename in _KNOWN_NAMES:
        return _KNOWN_NAMES[filename]
    stem = filename.removesuffix(".litertlm")
    return stem.replace("_", " ").replace("-", " ")


def _audio_supported(filename: str) -> bool:
    try:
        return bool(model_supports_audio(filename))
    except Exception:
        return False


def list_audio_models() -> list[str]:
    return [filename for filename in list_local_models() if _audio_supported(filename)]


def _resolve(saved: str | None, models: list[str]) -> str | None:
    if not models:
        return None
    if saved in models:
        return saved
    if DEFAULT_FILENAME in models:
        return DEFAULT_FILENAME
    return models[0]


def get_selected_chat_model() -> str | None:
    global _session_chat_model
    models = list_local_models()
    selected = _resolve(_session_chat_model, models)
    if selected is not None and _session_chat_model is not None:
        return selected
    selected = _resolve(get_setting(CHAT_MODEL_SETTING_KEY), models)
    _session_chat_model = selected
    return selected


def get_selected_live_model() -> str | None:
    global _session_live_model
    models = list_audio_models()
    selected = _resolve(_session_live_model, models)
    if selected is not None and _session_live_model is not None:
        return selected
    selected = _resolve(get_setting(LIVE_MODEL_SETTING_KEY), models)
    _session_live_model = selected
    return selected


def set_selected_chat_model(filename: str) -> bool:
    global _session_chat_model
    if filename not in list_local_models():
        raise ValueError(f"Локальная модель не найдена: {filename}")
    _session_chat_model = filename
    return set_setting(CHAT_MODEL_SETTING_KEY, filename)


def set_selected_live_model(filename: str) -> bool:
    global _session_live_model
    if filename not in list_local_models():
        raise ValueError(f"Локальная модель не найдена: {filename}")
    if not _audio_supported(filename):
        raise ValueError("Для Live нужна модель LiteRT-LM с поддержкой аудиовхода.")
    _session_live_model = filename
    return set_setting(LIVE_MODEL_SETTING_KEY, filename)
