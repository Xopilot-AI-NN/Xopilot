"""
Файл: /App/services/chat_store.py
Описание: Высокоуровневый доступ к чатам/сообщениям поверх services.db (Rust БД).
    UI не дёргается с advanced_xopilot напрямую — только через эти функции,
    чтобы вся логика вокруг активного чата и демо-данных жила в одном месте.

    ОГРАНИЧЕНИЕ: текущая схема messages (id, chat_id, role, content, created_at)
    не хранит вложения/цитаты/ответы-на-сообщение — эти метаданные ещё не
    персистятся, поэтому демо-сообщения с quote/reply_to/файлами ниже упрощены до
    обычного текста — это придётся расширить в следующей миграции схемы, когда
    дойдёте до вложений/цитат.
"""

from typing import List, Optional, Tuple

try:
    from .db import get_db
except ImportError:
    from services.db import get_db  # type: ignore


_active_chat_id: Optional[int] = None


def get_or_create_active_chat_id() -> int:
    """ID последнего (самого нового) чата, либо новый, если чатов ещё нет.
    Кэшируется в памяти процесса — переключение между чатами (сайдбар чатов)
    пока не реализовано отдельно — это всегда «самый последний» чат.
    """
    global _active_chat_id
    if _active_chat_id is not None:
        return _active_chat_id

    db = get_db()
    chats = db.list_chats()  # [(id, title, created_at), ...] по убыванию created_at
    if chats:
        _active_chat_id = chats[0][0]
    else:
        _active_chat_id = db.create_chat("Новый чат")
    return _active_chat_id


def load_chat_messages(chat_id: int) -> List[Tuple[str, str]]:
    """[(role, content), ...] в хронологическом порядке."""
    db = get_db()
    return [(role, content) for (_id, role, content, _created_at) in db.get_messages(chat_id)]


def save_user_message(chat_id: int, text: str) -> None:
    get_db().add_message(chat_id, "user", text)


def save_ai_message(chat_id: int, text: str) -> None:
    get_db().add_message(chat_id, "ai", text)


def seed_demo_chat_if_empty() -> None:
    """Наполняет БД примером диалога ОДИН РАЗ — только если во всей БД ещё нет ни одного чата.
    Тестовые сообщения теперь живут здесь, в БД — а не захардкожены в UI-коде (App/app/message.py).
    """
    db = get_db()
    if db.list_chats():
        return

    chat_id = db.create_chat("Продолжение оформления")
    demo = [
        ("ai", "Zephyr: Чем займёмся сегодня?"),
        ("user", "Продолжим оформление приложения."),
        ("user", "Прикрепляю материалы для проверки."),
        ("user", "Да, именно этот вариант стоит оставить."),
        ("user", "Добавлю это в следующую версию."),
        ("ai", "Zephyr: Готов. Поддержу стиль, компоненты и логику в одном аккуратном интерфейсе."),
    ]
    for role, text in demo:
        db.add_message(chat_id, role, text)

    global _active_chat_id
    _active_chat_id = chat_id