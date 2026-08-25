"""
Файл: /App/app/chat.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Чат__
        клеится по середине выше строки для ввода в окне
"""



import flet as ft

def build_chat(controls: list) -> ft.Container:
    return ft.Container(
        expand=True,
        bgcolor=ft.Colors.TRANSPARENT,
        content=ft.ListView(
            expand=True,
            spacing=12,
            padding=ft.padding.Padding.only(left=4, top=4, right=4, bottom=12),
            controls=controls,
        ),
    )