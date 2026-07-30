"""
Файл: /App/app/buttons/settings.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __кнопка настройки__
        клеится в меню снизу чатов
"""


import flet as ft


def build_settings_button(on_click=None) -> ft.Container:
    return ft.Container(
        width=30,
        height=30,
        border_radius=15,
        border=ft.border.Border.all(2, "#ffffff"),
        bgcolor="#ff6666ff",
        alignment=ft.alignment.Alignment.CENTER,
        content=ft.Icon(
            ft.Icons.SETTINGS,
            color=ft.Colors.WHITE,
            size=15,
        ),
        on_click=on_click,
    )