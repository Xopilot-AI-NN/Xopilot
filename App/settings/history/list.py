"""
Файл: /App/settings/history/list.py
Описание: __Список истории__.
           Содержит вспомогательное описание данных текущего открытого чата.
"""

import flet as ft


def build_history_summary() -> ft.Text:
    return ft.Text(
        "Очистка удалит сообщения только текущего открытого чата.",
        size=11,
        color="#47747a",
    )
