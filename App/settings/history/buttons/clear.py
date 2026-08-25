"""
Файл: /App/settings/history/buttons/clear.py
Описание: Кнопка очистки истории текущего чата.
"""

import flet as ft


def build_clear_button(on_click) -> ft.FilledButton:
    return ft.FilledButton(
        "Очистить историю",
        icon=ft.Icons.DELETE_OUTLINE,
        on_click=on_click,
    )
