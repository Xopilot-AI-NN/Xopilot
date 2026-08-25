"""
Файл: /App/app/add_material.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __кнопка для добавления материалов__
        клеится справа по середине строки ввода
        при нажатии открывается плавующие меню с выбором что можно добавить
        Фото, Файлы, Папки, Чат, Программу и многое другое
"""


import flet as ft


def build_add_material_button(on_click=None) -> ft.Container:
    return ft.Container(
        width=38,
        height=38,
        border_radius=19,
        border=ft.border.Border.all(2, "#ffffff"),
        bgcolor="#ff6666ff",
        alignment=ft.alignment.Alignment.CENTER,
        content=ft.Icon(
            ft.Icons.ADD,
            color=ft.Colors.WHITE,
            size=22,
        ),
        on_click=on_click,
    )
