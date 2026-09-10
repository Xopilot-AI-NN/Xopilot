"""
Файл: App/services/llm.py
Рабочий локальный ИИ через LiteRT-LM (Google, litert-lm-api). Чистый Python, без Rust.
.litertlm НЕ скачивается автоматически — клади в App/data/models/.
Пример (Gemma 4 E2B, мультимодальная):
huggingface.co/litert-community/gemma-4-E2B-it-litert-lm
Блокирующие вызовы — через asyncio.to_thread. Мультимодальность ещё не подключена.
"""

import glob
import os
from typing import List, Optional

try:
    from .stats import record_generation
except ImportError:
    from services.stats import record_generation  # type: ignore

try:
    import litert_lm

    _IMPORT_ERROR: Optional[Exception] = None
except Exception as exc:  # noqa: BLE001
    litert_lm = None  # type: ignore
    _IMPORT_ERROR = exc


MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "models")
DEFAULT_FILENAME = "gemma-4-E2B-it.litertlm"
DEFAULT_SYSTEM_PROMPT = "Ты — Zephyr, полезный ассистент в Xopilot. Отвечай кратко и по делу."

_engine = None
_conversation = None
_loaded_filename = None


def list_local_models():
    os.makedirs(MODELS_DIR, exist_ok=True)
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(MODELS_DIR, "*.litertlm")))


def is_model_loaded():
    return _engine is not None and _conversation is not None


def load_model(filename=DEFAULT_FILENAME, system_prompt=DEFAULT_SYSTEM_PROMPT):
    global _engine, _conversation, _loaded_filename

    if litert_lm is None:
        raise RuntimeError("litert_lm не установлен — выполните pip install litert-lm-api") from _IMPORT_ERROR

    path = os.path.join(MODELS_DIR, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Файл модели не найден: {path}. Положите .litertlm в App/data/models/")

    if _conversation is not None:
        _conversation.close()
    if _engine is not None:
        _engine.close()

    _engine = litert_lm.Engine(path, backend=litert_lm.Backend.CPU())
    _conversation = _engine.create_conversation(system_message=system_prompt)
    _loaded_filename = filename
    return filename


def _extract_text(result):
    try:
        parts = result.get("content") or []
        return "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    except AttributeError:
        return str(result)


def generate_reply(prompt_text, max_tokens=256):
    if _conversation is None:
        raise RuntimeError("Модель не загружена — вызовите load_model()")

    result = _conversation.send_message(prompt_text, max_output_tokens=max_tokens)
    text = _extract_text(result).strip()
    record_generation(text)
    return text