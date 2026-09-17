"""
Файл: /App/settings/abaut/main.py
Описание: __Страница «О приложении»__.
           Собирает сведения о версии, назначении и разработчике Xopilot.
"""

import flet as ft

from ..common import section_title
from .info import ABOUT_WIDTH, build_about_info, build_about_row


def build_about_page() -> ft.Column:
    about_content = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            tight=True,
            spacing=4,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                build_about_row(),
                build_about_info(),
            ],
        ),
    )

    return ft.Column(
        expand=True,
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(
                width=ABOUT_WIDTH,
                alignment=ft.Alignment.CENTER,
                content=section_title("О приложении"),
            ),
            about_content,
        ],
    )
