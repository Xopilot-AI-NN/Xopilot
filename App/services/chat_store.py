"""
Файл: /App/services/chat_store.py
Описание: Высокоуровневый доступ к чатам/сообщениям поверх services.db (Rust БД).
    UI не дёргается с advanced_xopilot напрямую — только через эти функции,
    чтобы вся бизнес-логика (активный чат, сидинг демо-данных) жила в одном месте.

    Сообщения теперь несут quote/reply_to/attachments (схема v2). Вложение хранятся как
    (имя, путь_к_файлу) — файл должен реально существовать на диске по этому пути,
    иначе Flet (`file_from_path`) просто не отрисует превью при загрузке истории.
"""

import os
from typing import List, Optional, Tuple

try:
    from .db import get_db, _app_data_dir
except ImportError:
    from services.db import get_db, _app_data_dir  # type: ignore


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


def load_chat_messages(chat_id: int):
    """Список advanced_xopilot.PyMessage в хронологическом порядке.
    Поля: id, role, content, quote, reply_to, attachments ([(name, path), ...]), created_at.
    """
    return get_db().get_messages(chat_id)


def save_user_message(
    chat_id: int,
    text: str,
    quote: Optional[str] = None,
    reply_to: Optional[str] = None,
    attachments: Optional[List[Tuple[str, str]]] = None,
) -> int:
    """Сохраняет сообщение пользователя, возвращает id новой строки (нужен в UI для последующего редактирования)."""
    return get_db().add_message(chat_id, "user", text, quote, reply_to, attachments or [])


def save_ai_message(chat_id: int, text: str) -> int:
    return get_db().add_message(chat_id, "ai", text)


def update_message(message_id: int, text: str) -> bool:
    """Правит текст уже сохранённого сообщения (редактирование в UI). Цитату/ответ/вложения пока не трогает."""
    return get_db().update_message(message_id, text)


def seed_demo_chat_if_empty() -> None:
    """Наполняет БД примером диалога ОДИН РАЗ — только если во всей БД ещё нет ни одного чата.
    Тестовые сообщения теперь живут здесь, в БД — а не захардкожены в UI-коде (App/app/message.py).

    ПРИМЕЧАНИЕ: точный текст исходного хардкоженного демо (до моего вмешательства) не сохранился —
    это новый пример, показывающий те же возможности (цитата, ответ, вложение).
    """
    db = get_db()
    if db.list_chats():
        return

    chat_id = db.create_chat("Продолжение оформления")

    db.add_message(chat_id, "ai", "Zephyr: Чем займёмся сегодня?")
    db.add_message(chat_id, "user", "Продолжим оформление приложения.")

    # пример вложения — реальный файл на диске, иначе Flet не отрисует превью
    demo_file_path = os.path.join(_app_data_dir(), "demo_attachment.txt")
    try:
        with open(demo_file_path, "w", encoding="utf-8") as f:
            f.write("Пример материала для проверки.\n")
    except OSError:
        demo_file_path = None

    db.add_message(
        chat_id,
        "user",
        "Прикрепляю материалы для проверки.",
        None,
        None,
        [("demo_attachment.txt", demo_file_path)] if demo_file_path else [],
    )

    # пример цитаты
    db.add_message(
        chat_id,
        "user",
        "Да, именно этот вариант стоит оставить.",
        "Zephyr: Чем займёмся сегодня?",
        None,
        [],
    )

    # пример ответа на сообщение
    db.add_message(
        chat_id,
        "user",
        "Добавлю это в следующую версию.",
        None,
        "Прикрепляю материалы для проверки.",
        [],
    )

    db.add_message(chat_id, "ai", "Zephyr: Готов. Поддержу стиль, компоненты и логику в одном аккуратном интерфейсе.")

    global _active_chat_id
    _active_chat_id = chat_id