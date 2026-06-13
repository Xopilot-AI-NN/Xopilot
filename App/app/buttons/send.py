"""
Файл: /App/app/buttons/send.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __кнопка отправить__
        клеится в строке для ввода справа по середине
"""


import flet as ft

def build_send_button(on_click) -> ft.Container:
    return ft.Container(
        width=38,
        height=38,
        border_radius=19,
        border=ft.border.Border.all(2, "#ffffff"),
        bgcolor="#ff6666ff",
        alignment=ft.alignment.Alignment.CENTER,
        content=ft.Image(
            src="Icons/icon_buttons/icon_send_button.svg",
            width=20,
            height=20,
        ),
        on_click=on_click,
    )
