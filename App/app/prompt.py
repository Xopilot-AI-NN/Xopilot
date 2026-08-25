"""
Файл: /App/app/prompt.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Строка ввода__
        клеится снизу в окне.
        через @ можно более детальнее указывать что использовать и при каком случае
        Фото, Файлы, Папки, Чат, Программу и многое другое
"""


import flet as ft

from .buttons.add_material import build_add_material_button
from .buttons.live import build_live_button
from .buttons.send import build_send_button


def build_prompt() -> ft.TextField:
    return ft.TextField(
        multiline=True,
        min_lines=1,
        max_lines=3,
        border_radius=10,
        bgcolor=ft.Colors.TRANSPARENT,
        color=ft.Colors.BLACK,
        cursor_color=ft.Colors.BLACK,
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=ft.Colors.TRANSPARENT,
        content_padding=ft.padding.Padding.symmetric(horizontal=4, vertical=8),
        expand=True,
    )


def build_prompt_container(
    prompt: ft.TextField,
    on_send,
    on_add_material=None,
    attachments: ft.Control | None = None,
) -> ft.Container:
    input_row = ft.Row(
        expand=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=8,
        controls=[
            build_add_material_button(on_click=on_add_material),
            prompt,
            build_live_button(),
            build_send_button(on_send),
        ],
    )

    return ft.Container(
        border_radius=10,
        border=ft.border.Border.all(2, "#00c753"),
        bgcolor="#d9ffe6",
        padding=ft.padding.Padding.symmetric(horizontal=8, vertical=4),
        content=ft.Column(
            spacing=4,
            controls=[
                attachments or ft.Container(height=0),
                input_row,
            ],
        ),
    )
