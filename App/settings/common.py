"""
Файл: /App/settings/common.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Общие элементы Android-style настроек.
           Здесь находятся единые заголовки разделов и строки параметров,
           чтобы все страницы имели одинаковый внешний вид.
"""

import flet as ft
try:
    from ..app.theme.palette import color
    from ..app.menu.buttons.brand import style_brand_button
    from ..app.theme.button_colors import action_role
except ImportError:
    from app.theme.palette import color
    from app.menu.buttons.brand import style_brand_button
    from app.theme.button_colors import action_role


def section_title(text: str) -> ft.Container:
    return ft.Container(
        padding=ft.Padding.only(left=4, top=14, bottom=5),
        content=ft.Text(text, size=13, color=color("#087f8c"), weight=ft.FontWeight.BOLD),
    )


def setting_row(icon, title: str, subtitle: str, trailing=None, on_click=None) -> ft.Container:
    controls = [
        style_brand_button(ft.Container(
            width=40,
            height=40,
            border_radius=14,
            bgcolor=color("#dff8f3"),
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(icon, size=20, color=color("#087f8c")),
        ), action_role(icon, title)),
        ft.Column(
            expand=True,
            spacing=2,
            controls=[
                ft.Text(title, size=14, color=color("#123b43"), weight=ft.FontWeight.W_500),
                ft.Text(subtitle, size=12, color=color("#47747a"), max_lines=2),
            ],
        ),
    ]
    stacked = isinstance(trailing, ft.Dropdown)
    if trailing is not None and not stacked:
        controls.append(trailing)
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        bgcolor=color("#f3fffc"),
        border_radius=18,
        ink=on_click is not None,
        on_click=on_click,
        content=(ft.Column(spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                           controls=[ft.Row(spacing=11, controls=controls), trailing]) if stacked else
                 ft.Row(spacing=11, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=controls)),
    )
