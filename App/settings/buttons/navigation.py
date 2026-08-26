"""
Файл: /App/settings/buttons/navigation.py
Описание: Кнопка перехода между страницами настроек.
"""

import flet as ft


def build_navigation_button(icon, label: str, subtitle: str, on_click) -> ft.Container:
    return ft.Container(
        height=62,
        padding=ft.padding.Padding.symmetric(horizontal=10, vertical=8),
        border_radius=10,
        ink=True,
        on_click=on_click,
        content=ft.Row(
            spacing=11,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
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
                        ft.Text(label, size=13, color="#123b43"),
                        ft.Text(subtitle, size=11, color="#47747a", max_lines=2),
                    ],
                ),
                ft.Icon(ft.Icons.CHEVRON_RIGHT, color="#47747a"),
            ],
        ),
    )
