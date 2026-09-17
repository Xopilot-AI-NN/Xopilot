"""
Файл: App/app/buttons/microphone.py
Разработчик: DenBroLiik
Описание: Кнопка диктовки текста в поле ввода.
"""

import flet as ft


def build_microphone_button(on_click=None):
    return ft.Container(
        width=38,
        height=38,
        border_radius=19,
        border=ft.Border.all(2, "#ffffff"),
        bgcolor="#ff6666ff",
        alignment=ft.Alignment.CENTER,
        tooltip="Диктовка",
        content=ft.Icon(ft.Icons.MIC, color=ft.Colors.WHITE, size=20),
        on_click=on_click,
    )
