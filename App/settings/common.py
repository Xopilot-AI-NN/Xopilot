"""
Файл: /App/settings/common.py
Описание: Общие элементы Android-style настроек.
           Здесь находятся единые заголовки разделов и строки параметров,
           чтобы все страницы имели одинаковый внешний вид.
"""

import flet as ft


def section_title(text: str) -> ft.Container:
    return ft.Container(
        padding=ft.padding.Padding.only(left=4, top=14, bottom=5),
        content=ft.Text(text.upper(), size=11, color="#087f8c", weight=ft.FontWeight.BOLD),
    )


def setting_row(icon, title: str, subtitle: str, trailing=None, on_click=None) -> ft.Container:
    controls = [
        ft.Container(
            width=36,
            height=36,
            border_radius=18,
            bgcolor="#dff8f3",
            alignment=ft.alignment.Alignment.CENTER,
            content=ft.Icon(icon, size=19, color="#087f8c"),
        ),
        ft.Column(
            expand=True,
            spacing=2,
            controls=[
                ft.Text(title, size=13, color="#123b43"),
                ft.Text(subtitle, size=11, color="#47747a", max_lines=2),
            ],
        ),
    ]
    if trailing is not None:
        controls.append(trailing)
    return ft.Container(
        height=62,
        padding=ft.padding.Padding.symmetric(horizontal=10, vertical=8),
        border_radius=10,
        ink=on_click is not None,
        on_click=on_click,
        content=ft.Row(spacing=11, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=controls),
    )
