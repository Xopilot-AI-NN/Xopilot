"""
Файл: /App/services/stats.py
Описание: Реальная статистика использования ИИ для страницы settings/account.

    Сообщения считаются напрямую из БД (total_message_count). Токены/время — приближённые
    (нет настоящего подсчёта токенов через токенизатор модели — счёт словами), но реально
    накапливаются по факту генерации (services/llm.py::generate_reply), а не захардкожено.
    Хранится в settings-таблице через get_setting/set_setting.
"""

try:
    from .db import get_db, get_setting, set_setting
except ImportError:
    from services.db import get_db, get_setting, set_setting  # type: ignore


_TOKENS_KEY = "stats_tokens_total"
_SECONDS_KEY = "stats_seconds_total"


def record_generation(text: str, seconds: float) -> None:
    """Вызывается после каждой успешной генерации ответа ИИ. Токены оцениваются грубо
    (кол-во слов в ответе) — без доступа к токенизатору модели точнее не считать.
    Тихо не падает UI, если БД недоступна.
    """
    try:
        approx_tokens = max(1, len(text.split()))
        current_tokens = int(get_setting(_TOKENS_KEY, "0") or "0")
        current_seconds = float(get_setting(_SECONDS_KEY, "0") or "0")
        set_setting(_TOKENS_KEY, str(current_tokens + approx_tokens))
        set_setting(_SECONDS_KEY, str(current_seconds + seconds))
    except Exception:
        pass


def get_stats():
    """{"messages": int, "tokens": int, "hours": float} -- при недоступной БД всё 0."""
    try:
        messages = get_db().total_message_count()
    except Exception:
        messages = 0
    tokens = int(get_setting(_TOKENS_KEY, "0") or "0")
    seconds = float(get_setting(_SECONDS_KEY, "0") or "0")
    return {"messages": messages, "tokens": tokens, "hours": seconds / 3600}
