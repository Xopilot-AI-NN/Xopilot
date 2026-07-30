"""
Файл: /App/app/workspaces.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __кнопка рабочих пространств__
        находится сверху чатов в меню
        можно создавать рабочии пространства для конкреткного проэкта
        в которых будут свои данные и материалы проэктов
"""


import flet as ft


def build_workspaces_button(on_click=None) -> ft.Container:
    return ft.Container(
        width=30,
        height=30,
        border_radius=15,
        border=ft.border.Border.all(2, "#ffffff"),
        bgcolor="#ff6666ff",
        alignment=ft.alignment.Alignment.CENTER,
        content=ft.Icon(
            ft.Icons.WORKSPACES,
            color=ft.Colors.WHITE,
            size=15,
        ),
        on_click=on_click,
    )