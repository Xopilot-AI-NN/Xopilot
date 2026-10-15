"""
Файл: /App/settings/buttons/navigation.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Кнопка перехода между страницами настроек.
"""

import flet as ft
try:
    from ...app.palette import color
    from ...app.buttons.brand import style_brand_button
    from ...app.button_colors import action_role
except ImportError:
    from app.palette import color
    from app.buttons.brand import style_brand_button
    from app.button_colors import action_role


def build_navigation_button(icon, label: str, subtitle: str, on_click) -> ft.Container:
    return ft.Container(
        padding=16,
        border_radius=22,
        bgcolor=color('#f3fffc'),
        ink=True,
        on_click=on_click,
        content=ft.Row(
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                style_brand_button(ft.Container(
                    width=44,
                    height=44,
                    border_radius=16,
                    bgcolor=color("#dff8f3"),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, size=24, color=color("#087f8c")),
                ), action_role(icon, label)),
                ft.Column(
                    expand=True,
                    spacing=3,
                    controls=[
                        ft.Text(label, size=15, color=color("#123b43"), weight=ft.FontWeight.W_600),
                        ft.Text(subtitle, size=12, color=color("#47747a"), max_lines=2),
                    ],
                ),
                ft.Icon(ft.Icons.CHEVRON_RIGHT, color=color("#47747a"), opacity=0.65),
            ],
        ),
    )
