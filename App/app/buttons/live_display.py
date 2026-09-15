"""
Файл: /App/app/buttons/live_display.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __кнопка голосового разговора Live Display__
        клеится в строке для доп функций
"""



import flet as ft


def build_live_button(on_click=None) -> ft.Container:
    return ft.Container(
        width=38,
        height=38,
        border_radius=19,
        border=ft.border.Border.all(2, "#ffffff"),
        bgcolor="#ff6666ff",
        alignment=ft.alignment.Alignment.CENTER,
        tooltip="Live — трансляция экрана",
        content=ft.Icon(
            ft.Icons.SMART_DISPLAY,
            color=ft.Colors.WHITE,
            size=20,
        ),
        on_click=on_click,
    )