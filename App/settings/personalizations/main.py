"""
Файл: /App/settings/personalizations/main.py
Описание: __Страница персонализации__.
           Объединяет настройки темы оформления и языка интерфейса.
"""

import flet as ft

from ..common import section_title, setting_row
from .buttons.language import build_language_select
from .buttons.theme import build_theme_switch


def build_personalizations_page(page: ft.Page, on_status) -> ft.Column:
    return ft.Column(
        spacing=2,
        controls=[
            section_title("Внешний вид"),
            setting_row(
                ft.Icons.DARK_MODE_OUTLINED,
                "Тёмная тема",
                "Переключить оформление приложения",
                build_theme_switch(page, on_status),
            ),
            setting_row(
                ft.Icons.LANGUAGE,
                "Язык интерфейса",
                "Выберите язык меню и сообщений",
                build_language_select(on_status),
            ),
        ],
    )
