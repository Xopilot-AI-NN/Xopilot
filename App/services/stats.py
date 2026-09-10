"""
Файл: /App/services/stats.py
Описание: Реальная статистика использования ИИ для страницы settings/account.

    Сообщения считаются напрямую из БД (total_message_count). Токены/время — приближённые
    (нет настоящего подсчёта токенов через токенизатор модели — счёт словами), но реально
    накапливаются по факту генерации (services/llm.py::generate_reply), а не захардкожено.
    Хранится в settings-таблице через get_setting/set_setting.
"""

import time

try:
    from .db import get_db, get_setting, set_setting
except ImportError:
    from services.db import get_db, get_setting, set_setting  # type: ignore


TOKENS_KEY = "stats_tokens_total"
APP_TIME_KEY = "stats_app_seconds_total"

_app_started_at = None


def start_app_session():
    # Запоминает момент запуска текущей сессии.
    global _app_started_at
    if _app_started_at is None:
        _app_started_at = time.monotonic()


def get_app_seconds():
    # Возвращает сохранённое время вместе с текущей сессией.
    stored = float(get_setting(APP_TIME_KEY, "0") or 0)
    if _app_started_at is None:
        return stored

    return stored + max(0, time.monotonic() - _app_started_at)


def persist_app_session():
    # Сохраняет время текущей сессии в базу.
    global _app_started_at
    if _app_started_at is None:
        return

    elapsed = max(0, time.monotonic() - _app_started_at)
    if elapsed == 0:
        return

    stored = float(get_setting(APP_TIME_KEY, "0") or 0)
    set_setting(APP_TIME_KEY, str(stored + elapsed))
    _app_started_at = time.monotonic()


def record_generation(text: str):
    # Добавляет примерное количество токенов ответа в статистику.
    try:
        tokens = max(1, len(text.split()))
        total = int(get_setting(TOKENS_KEY, "0") or 0)
        set_setting(TOKENS_KEY, str(total + tokens))
    except Exception:
        pass


def get_stats():
    # Собирает основную статистику для страницы аккаунта.
    try:
        messages = get_db().total_message_count()
    except Exception:
        messages = 0

    try:
        tokens = int(get_setting(TOKENS_KEY, "0") or 0)
    except Exception:
        tokens = 0

    try:
        app_seconds = get_app_seconds()
    except Exception:
        app_seconds = 0

    return {
        "messages": messages,
        "tokens": tokens,
        "app_seconds": app_seconds,
    }