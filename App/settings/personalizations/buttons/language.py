"""
Файл: /App/settings/personalizations/buttons/language.py
Описание: Кнопка выбора языка интерфейса.
"""

import flet as ft


def build_language_select(on_status) -> ft.Dropdown:
    select = ft.Dropdown(
        value="ru",
        width=122,
        dense=True,
        options=[
            ft.DropdownOption(key="ru", text="Русский"),
            ft.DropdownOption(key="en", text="English"),
        ],
    )
    select.on_select = lambda _: on_status("Язык сохранён для текущего запуска")
    return select
