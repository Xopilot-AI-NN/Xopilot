"""
Файл: /App/services/llm.py
Описание: Рабочий локальный ИИ — обёртка над advanced_xopilot.PyLlm (candle/candelabra, GGUF).

    GGUF-файл НЕ скачивается автоматически — клади его вручную в App/data/models/.
    Токенизатор (маленький tokenizer.json) тянется с Hugging Face автоматически.

    Загрузка/генерация — блокирующие вызовы, вызывающий код должен запускать через
    asyncio.to_thread(...), иначе UI замрёт на время загрузки/генерации.
"""

import glob
import os
from typing import List, Optional

try:
    import advanced_xopilot  # type: ignore

    _IMPORT_ERROR: Optional[Exception] = None
except Exception as exc:  # noqa: BLE001 — модуль может быть ещё не собран
    advanced_xopilot = None  # type: ignore
    _IMPORT_ERROR = exc


MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "models")

# модель по умолчанию — Phi-4-mini-instruct, Q4_K_M (~2.5 ГБ), комфортно вмещается в 6 ГБ.
# Файл надо положить вручную в MODELS_DIR (см. bartowski/microsoft_Phi-4-mini-instruct-GGUF на HF).
DEFAULT_FILENAME = "microsoft_Phi-4-mini-instruct-Q4_K_M.gguf"
DEFAULT_TOKENIZER_REPO = "microsoft/Phi-4-mini-instruct"
DEFAULT_SYSTEM_PROMPT = "Ты — Zephyr, полезный ассистент в Xopilot. Отвечай кратко и по делу."

_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        if advanced_xopilot is None:
            raise RuntimeError(
                "advanced_xopilot не собран — выполните `maturin develop` в Services/"
            ) from _IMPORT_ERROR
        _llm = advanced_xopilot.PyLlm()
    return _llm


def list_local_models() -> List[str]:
    """Имена .gguf-файлов, уже лежащих в App/data/models/."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(MODELS_DIR, "*.gguf")))


def is_model_loaded() -> bool:
    try:
        return _get_llm().is_loaded()
    except Exception:
        return False


def load_model(filename: str = DEFAULT_FILENAME, tokenizer_repo: str = DEFAULT_TOKENIZER_REPO) -> str:
    """Загружает модель из App/data/models/<filename>. Возвращает архитектуру (напр. "phi3").
    Блокирующий вызов — вызывать через asyncio.to_thread из UI.
    """
    path = os.path.join(MODELS_DIR, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Файл модели не найден: {path}. Положите .gguf в App/data/models/"
        )
    return _get_llm().load(path, tokenizer_repo)


def generate_reply(prompt_text: str, system_prompt: str = DEFAULT_SYSTEM_PROMPT, max_tokens: int = 256) -> str:
    """prompt_text — сырое сообщение пользователя. Шаблон phi-3-chat собирается здесь —
    подходит для Phi-3/Phi-4 (текущий дефолт). Для других семейств (Gemma/Qwen и т.д.) шаблон
    иной — это будет нужно учесть отдельно при смене модели.
    Блокирующий вызов — вызывать через asyncio.to_thread из UI.
    """
    formatted = f"<|system|>{system_prompt}<|end|><|user|>{prompt_text}<|end|><|assistant|>"
    return _get_llm().generate(formatted, max_tokens)