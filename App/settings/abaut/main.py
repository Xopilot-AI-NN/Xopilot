"""
Файл: /App/settings/abaut/main.py
Описание: __Страница «О приложении»__.
           Собирает сведения о версии, назначении и разработчике Xopilot.
"""

import flet as ft

from ..common import section_title
from .info import build_about_info, build_about_row


def build_about_page() -> ft.Column:
    return ft.Column(
        width=455,
        alignment=ft.MainAxisAlignment.START,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=2,
        controls=[
            section_title("О приложении"),
            build_about_row(),
            build_about_info(),
        ],
    )
