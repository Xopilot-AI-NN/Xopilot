"""
Файл: /App/settings/history/main.py
Описание: __Страница истории чатов__.
           Отчистка теперь реально удаляет сообщения из БД (раньше чистила только UI —
           сообщения возвращались после перезагрузки аппа).
"""

import flet as ft

from ..common import section_title, setting_row
from .buttons.clear import build_clear_button
from .list import build_history_summary

try:
    from ...services.chat_store import clear_chat_messages
except ImportError:
    from services.chat_store import clear_chat_messages


def build_history_page(chat_list: ft.ListView | None, on_status, chat_id: int | None = None) -> ft.Column:
    def clear(_):
        if chat_id is not None:
            try:
                clear_chat_messages(chat_id)
            except Exception:
                pass  # БД недоступна — в следующий раз открытия старые сообщения всё равно вернутся
        if chat_list is not None:
            chat_list.controls.clear()
            chat_list.update()
        on_status("История текущего чата очищена")

    return ft.Column(
        spacing=2,
        controls=[
            section_title("Данные"),
            setting_row(
                ft.Icons.DELETE_OUTLINE,
                "Очистить историю",
                "Удалить сообщения текущего открытого чата",
                ft.Icon(ft.Icons.CHEVRON_RIGHT, color="#47747a"),
                clear,
            ),
            ft.Container(padding=ft.padding.Padding.only(left=47, bottom=5), content=build_clear_button(clear)),
            build_history_summary(),
        ],
    )