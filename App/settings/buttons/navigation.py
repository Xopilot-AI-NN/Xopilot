"""
Файл: /App/settings/buttons/navigation.py
Описание: Кнопка перехода между страницами настроек.
"""

import flet as ft


def build_navigation_button(icon, label: str, subtitle: str, on_click) -> ft.Container:
    return ft.Container(
        height=74,
        padding=ft.padding.Padding.symmetric(horizontal=14, vertical=10),
        border_radius=12,
        ink=True,
        on_click=on_click,
        content=ft.Row(
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=44,
                    height=44,
                    border_radius=22,
                    bgcolor="#dff8f3",
                    alignment=ft.alignment.Alignment.CENTER,
                    content=ft.Icon(icon, size=24, color="#087f8c"),
                ),
                ft.Column(
                    expand=True,
                    spacing=3,
                    controls=[
                        ft.Text(label, size=15, color="#123b43", weight=ft.FontWeight.W_600),
                        ft.Text(subtitle, size=12, color="#47747a", max_lines=2),
                    ],
                ),
                ft.Icon(ft.Icons.CHEVRON_RIGHT, color="#47747a"),
            ],
        ),
    )
