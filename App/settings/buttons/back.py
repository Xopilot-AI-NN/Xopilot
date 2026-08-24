"""
Файл: /App/settings/buttons/back.py
Описание: Кнопка возврата на главную страницу настроек.
"""

import flet as ft


def build_back_button(on_click) -> ft.IconButton:
    return ft.IconButton(
        icon=ft.Icons.ARROW_BACK,
        icon_color=ft.Colors.WHITE,
        tooltip="Назад к настройкам",
        visible=False,
        on_click=on_click,
    )
