"""
Файл: /App/app/buttons/new_chat.py
Разработчик: DenBroLiik, Claude
Версия: 2.0.0
Описание: __кнопка нового чата__
        клеится в меню слева от чата, сразу под кнопкой меню
        начинает новый диалог
"""

import flet as ft

SIZE_MIN = 44
SIZE_MAX = 54
ICON_MIN = 22
ICON_MAX = 28


def build_new_chat_button(on_click=None, size: int = 40, icon_size: int = 20) -> ft.Container:
    button = ft.Container(
        width=size,
        height=size,
        border_radius=size / 2,
        border=ft.border.Border.all(2, "#ffffff"),
        bgcolor="#ff6666ff",
        alignment=ft.alignment.Alignment.CENTER,
        ink=True,
        animate=ft.Animation(duration=150, curve=ft.AnimationCurve.EASE_OUT),
        content=ft.Icon(
            ft.Icons.ADD_COMMENT,
            color=ft.Colors.WHITE,
            size=icon_size,
        ),
        on_click=on_click,
    )

    def handle_hover(e: ft.Event[ft.Container]):
        e.control.border = ft.border.Border.all(2, "#d9ffe6" if e.data else "#ffffff")
        e.control.update()

    button.on_hover = handle_hover
    return button


def resize_new_chat_button(button: ft.Container, ratio: float) -> None:
    ratio = max(0.0, min(1.0, ratio))
    size = round(SIZE_MIN + (SIZE_MAX - SIZE_MIN) * ratio)
    icon_size = round(ICON_MIN + (ICON_MAX - ICON_MIN) * ratio)
    button.width = size
    button.height = size
    button.border_radius = size / 2
    if isinstance(button.content, ft.Icon):
        button.content.size = icon_size
    button.update()