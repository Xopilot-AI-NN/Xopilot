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
        width=48,
        height=48,
        border_radius=24,
        border=ft.Border.all(2, "#ffffff"),
        bgcolor="#ff6666ff",
        alignment=ft.Alignment.CENTER,
        tooltip="Отправить сообщение",
        content=ft.Image(
            src="Icons/icon_buttons/icon_send_button.svg",
            width=20,
            height=20,
        ),
        on_click=on_click,
    )
