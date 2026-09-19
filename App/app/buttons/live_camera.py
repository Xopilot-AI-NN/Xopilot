"""
Файл: /App/app/buttons/live_camera.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __кнопка голосового разговора Live Camera__
        клеится в строке для доп функций
"""


import flet as ft


def build_live_camera_button(on_click=None, active: bool = False) -> ft.Container:
    return ft.Container(
        width=38,
        height=38,
        border_radius=19,
        border=ft.Border.all(3 if active else 2, "#00c753" if active else "#ffffff"),
        bgcolor="#ff6666ff",
        alignment=ft.Alignment.CENTER,
        tooltip="Live — камера включена" if active else "Live — показать с камеры",
        content=ft.Icon(
            ft.Icons.CAMERA,
            color=ft.Colors.WHITE,
            size=20,
        ),
        on_click=on_click,
    )