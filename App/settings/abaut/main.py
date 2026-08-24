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
        spacing=2,
        controls=[
            section_title("О приложении"),
            build_about_row(),
            ft.Container(
                padding=ft.padding.Padding.only(left=47, right=10, bottom=8),
                content=build_about_info(),
            ),
        ],
    )
