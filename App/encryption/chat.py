"""
Файл: /App/encryption/chat.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Чат__
        клеится по середине выше строки для ввода в окне
"""



import flet as ft

def build_chat(controls: list) -> ft.Container:
    return ft.Container(
        expand=True,
        bgcolor="#00c753",
        border_radius=8,
        border=ft.border.Border.all(2, "#d9ffe6"),
        content=ft.ListView(
            expand=True,
            spacing=20,
            padding=ft.padding.Padding.all(4),
            controls=controls,
        ),
    )
