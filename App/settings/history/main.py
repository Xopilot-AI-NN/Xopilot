"""
Файл: /App/settings/history/main.py
Описание: __Страница истории чатов__.
           Отчистка теперь реально удаляет сообщения из БД (раньше чистила только UI —
           сообщения возвращались после перезагрузки аппа).
"""

import flet as ft
try:
    from ...app.palette import color
except ImportError:
    from app.palette import color

from ..common import section_title, setting_row
from .buttons.clear import build_clear_button
from .list import build_history_summary, build_history_list

try:
    from ...services.chat_store import clear_chat_messages
except ImportError:
    from services.chat_store import clear_chat_messages


def build_history_page(chat_list: ft.ListView | None, on_status, chat_id: int | None = None, on_clear=None, page=None, on_select=None) -> ft.Column:
    def clear(_):
        try:
            if on_clear is not None:
                on_clear()
            else:
                if chat_id is None:
                    raise RuntimeError("Чат недоступен")
                clear_chat_messages(chat_id)
                if chat_list is not None:
                    chat_list.controls.clear()
                    chat_list.update()
        except Exception as exc:
            on_status(f"Не удалось очистить историю: {exc}")
            return
        on_status("История текущего чата очищена")

    def confirm_clear(e):
        if page is None:
            clear(e)
            return
        def confirm(_):
            page.pop_dialog()
            clear(e)
        page.show_dialog(ft.AlertDialog(bgcolor=color("#eafffa"), title=ft.Text("Очистить текущий чат?", color=color("#123b43")),
            content=ft.Text("Все его сообщения будут удалены. Сначала можно экспортировать чат кнопкой в его заголовке.", color=color("#47747a")),
            actions=[ft.TextButton(content="Отмена", on_click=lambda _: page.pop_dialog()),
                     ft.FilledButton(content="Очистить", on_click=confirm)]))

    return ft.Column(
        spacing=2,
        controls=[
            *([build_history_list(page, on_select)] if page is not None else []),
            section_title("Данные"),
            setting_row(
                ft.Icons.DELETE_OUTLINE,
                "Очистить историю",
                "Удалить сообщения текущего открытого чата",
                ft.Icon(ft.Icons.CHEVRON_RIGHT, color=color("#47747a")),
                confirm_clear,
            ),
            ft.Container(padding=ft.Padding.only(left=47, bottom=5), content=build_clear_button(confirm_clear)),
            build_history_summary(),
        ],
    )
