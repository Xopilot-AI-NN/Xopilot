"""
Файл: /App/app/buttons/menu.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __кнопка меню__
        клеится в окне сверху слева от чата
        при клике открывает меню
"""


import flet as ft


def build_menu_button(on_click=None) -> ft.Container:
    return ft.Container(
        width=30,
        height=30,
        border_radius=15,
        border=ft.border.Border.all(2, "#ffffff"),
        bgcolor="#ff6666ff",
        alignment=ft.alignment.Alignment.CENTER,
        content=ft.Icon(
            ft.Icons.MENU,
            color=ft.Colors.WHITE,
            size=16,
        ),
        on_click=on_click,
    )