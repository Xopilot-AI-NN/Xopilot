"""
Файл: /App/settings/abaut/main.py
Описание: __Страница «О приложении»__.
           Собирает сведения о версии, назначении и разработчике Xopilot.
"""

import flet as ft

from ..common import section_title
from .info import ABOUT_WIDTH, build_about_info, build_about_row


def build_about_page(page=None) -> ft.Column:
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
                *([ft.TextButton(content='Поддержка',icon=ft.Icons.SUPPORT_AGENT,
                    on_click=lambda _:__import__('importlib').import_module(
                        'App.services.support' if __package__.startswith('App.') else 'services.support').open_support(page))] if page is not None else []),
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
