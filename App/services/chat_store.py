"""
Файл: /App/services/chat_store.py
Описание: Высокоуровневый доступ к чатам/сообщениям поверх services.db (Rust БД).
    UI не дёргается с advanced_xopilot напрямую — только через эти функции,
    чтобы вся бизнес-логика (активный чат, очистка старых заглушек) жила в одном месте.

    Сообщения теперь несут quote/reply_to/attachments (схема v2). Вложение хранятся как
    (имя, путь_к_файлу) — файл должен реально существовать на диске по этому пути,
    иначе Flet (`file_from_path`) просто не отрисует превью при загрузке истории.
"""

import os
import json
from typing import List, Optional, Tuple

try:
    from .db import get_db
except ImportError:
    from services.db import get_db  # type: ignore


_active_chat_id: Optional[int] = None


def get_or_create_active_chat_id() -> int:
    """ID активного чата (кэшируется в памяти процесса). Если ещё ничего не выбирался
    через switch_active_chat()/create_new_chat() в этой сессии — возвращает самый новый чат,
    либо создаёт новый, если чатов ещё нет.
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
    assert _active_chat_id is not None
    return _active_chat_id


def switch_active_chat(chat_id: int) -> None:
    """Переключает активный чат (выбор чата в сайдбаре). Не проверяет,
    что chat_id действительно существует — это ответственность вызывающего (chat_id берётся из list_chat_items()).
    """
    global _active_chat_id
    _active_chat_id = chat_id


def create_new_chat(title: str = "Новый чат") -> int:
    """Создаёт новый пустой чат и делает его активным. Возвращает id нового чата."""
    global _active_chat_id
    chat_id = get_db().create_chat(title)
    _active_chat_id = chat_id
    return chat_id


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


def delete_message(message_id: int) -> bool:
    """Удаляет одно сообщение (вложения — каскадно). Возвращает False, если id не найден."""
    return get_db().delete_message(message_id)


def delete_chat(chat_id: int) -> bool:
    """Удаляет чат целиком (сообщения и вложения — каскадно). Если удаляемый чат был активным,
    сбрасывает кэш активного чата — вызывающий должен сам выбрать следующий активный чат
    (через switch_active_chat/create_new_chat).
    """
    global _active_chat_id
    deleted = get_db().delete_chat(chat_id)
    if _active_chat_id == chat_id:
        _active_chat_id = None
    return deleted


_LEGACY_CLEANUP_KEY = "legacy_demo_messages_removed_v1"
_LEGACY_REPLIES = {
    "Понимаю, звучит не очень. Чем могу помочь?",
    "Принято. Продолжаем?",
    "Здорово! Рад, что всё идёт хорошо.",
}
_LEGACY_DEMO = (
    ("ai", "Zephyr: Чем займёмся сегодня?", None, None),
    ("user", "Продолжим оформление приложения.", None, None),
    ("user", "Прикрепляю материалы для проверки.", None, None),
    ("user", "Да, именно этот вариант стоит оставить.", "Zephyr: Чем займёмся сегодня?", None),
    ("user", "Добавлю это в следующую версию.", None, "Прикрепляю материалы для проверки."),
    ("ai", "Zephyr: Готов. Поддержу стиль, компоненты и логику в одном аккуратном интерфейсе.", None, None),
)


def _is_legacy_demo_prefix(title, messages):
    if title != "Продолжение оформления" or len(messages) < len(_LEGACY_DEMO):
        return False
    for index, (message, expected) in enumerate(zip(messages, _LEGACY_DEMO)):
        if (message.role, message.content, message.quote, message.reply_to) != expected:
            return False
        attachments = message.attachments
        if index == 2:
            if attachments and (len(attachments) != 1 or attachments[0][0] != "demo_attachment.txt"
                                or os.path.basename(attachments[0][1]) != "demo_attachment.txt"):
                return False
        elif attachments:
            return False
    return True


def cleanup_legacy_messages():
    """Разовая очистка точного демо-префикса и трёх ответов старого классификатора.

    Пользовательские сообщения с такими же словами, изменённый демо-диалог и все
    последующие реальные реплики сохраняются. Файлы пользователя не удаляются.
    """
    db = get_db()
    if db.get_setting(_LEGACY_CLEANUP_KEY) == "1":
        return 0
    delete = getattr(db, "delete_message", None)
    if delete is None:
        # Старые сборки нативного модуля продолжают открывать историю. После
        # обновления модуля очистка повторится, поскольку маркер ещё не записан.
        return 0
    ids = set()
    by_id = {}
    for chat_id, title, _ in db.list_chats():
        messages = db.get_messages(chat_id)
        by_id.update((message.id, message) for message in messages)
        if _is_legacy_demo_prefix(title, messages):
            ids.update(message.id for message in messages[:len(_LEGACY_DEMO)])
        ids.update(message.id for message in messages
                   if message.role == "ai" and message.content in _LEGACY_REPLIES
                   and not message.quote and not message.reply_to and not message.attachments)

    def signature(message):
        return json.dumps([message.role, message.content, message.quote, message.reply_to,
                           message.attachments], ensure_ascii=False)

    pending_key = _LEGACY_CLEANUP_KEY + ".pending"
    pending = json.loads(db.get_setting(pending_key) or "{}")
    # После частичного сбоя продолжаем только неизменённые строки прежнего плана.
    # Это важно для демо-префикса: после удаления его начала он уже не совпадёт целиком.
    for key, expected in pending.items():
        message = by_id.get(int(key))
        if message is not None and signature(message) == expected:
            ids.add(message.id)
    if ids:
        db.set_setting(pending_key, json.dumps({str(i): signature(by_id[i]) for i in ids}, ensure_ascii=False))
    deleted = sum(bool(delete(message_id)) for message_id in sorted(ids))
    db.set_setting(_LEGACY_CLEANUP_KEY, "1")
    db.set_setting(pending_key, "")
    return deleted


def list_chat_items():
    """Реальные (chat_id, название, количество сообщений, pinned) для списка чатов в сайдбаре.
    Упорядочено по дате создания по убыванию (самый новый чат — первым).
    """
    db = get_db()
    return [(chat_id, title or "Новый чат", f"Сообщений: {len(db.get_messages(chat_id))}", False)
            for chat_id, title, _ in db.list_chats()]


def clear_chat_messages(chat_id):
    """Стирает все сообщения чата из БД (вложения — каскадно). Сам чат остаётся."""
    get_db().clear_chat_messages(chat_id)