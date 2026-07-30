"""
Файл: /App/app/buttons/live.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __кнопка разговора в реальном времени__
        клеится в строке для ввода от кнопки отправить
"""


import flet as ft


def build_live_button(on_click=None) -> ft.Container:
    return ft.Container(
        width=38,
        height=38,
        border_radius=19,
        border=ft.border.Border.all(2, "#ffffff"),
        bgcolor="#ff6666ff",
        alignment=ft.alignment.Alignment.CENTER,
        content=ft.Icon(
            ft.Icons.MIC,
            color=ft.Colors.WHITE,
            size=20,
        ),
        on_click=on_click,
    )
