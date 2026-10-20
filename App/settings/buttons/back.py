"""
Файл: /App/settings/buttons/back.py
Описание: Кнопка возврата на главную страницу настроек.
"""

import flet as ft
try:
    from ...app.theme.palette import color
except ImportError:
    from app.theme.palette import color


def build_back_button(on_click) -> ft.IconButton:
    return ft.IconButton(
        icon=ft.Icons.ARROW_BACK,
        icon_color=color("#123b43"),
        tooltip="Назад к настройкам",
        visible=False,
        on_click=on_click,
    )
