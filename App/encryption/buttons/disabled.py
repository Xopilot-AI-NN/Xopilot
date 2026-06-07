"""
Файл: /App/encryption/buttons/disabled.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __кнопка отклонения__
        клеится в чате ниже сообщения
"""



import flet as ft

def build_close_button(on_click) -> ft.Container:
    return ft.Container(
        width=27,
        height=27,
        border_radius=4,
        border=ft.border.Border.all(2, "#d9ffe6"),
        gradient=ft.LinearGradient(
            begin=ft.alignment.Alignment.TOP_LEFT,
            end=ft.alignment.Alignment.BOTTOM_RIGHT,
            colors=["#7300ff", "#9900ff"],
        ),
        alignment=ft.alignment.Alignment.CENTER,
        content=ft.Icon(
            ft.Icons.CLOSE,
            color=ft.Colors.WHITE,
            size=18,
        ),
        on_click=on_click,
    )
