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
from .buttons.microphone import build_microphone_button
from .buttons.send import build_send_button


def build_prompt(on_submit=None) -> ft.TextField:
    return ft.TextField(
        on_submit=on_submit,
        multiline=True,
        shift_enter=True,
        min_lines=1,
        max_lines=3,
        # Flet 1.x: borderless filled field. The visible outline belongs to
        # build_prompt_container(), not to TextField itself.
        filled=True,
        bgcolor="#d9ffe6",
        focused_bgcolor="#d9ffe6",
        border=ft.NoInputBorder(),
        color=ft.Colors.BLACK,
        cursor_color=ft.Colors.BLACK,
        content_padding=ft.Padding.symmetric(horizontal=4, vertical=8),
        expand=True,
    )


def build_prompt_container(
    prompt: ft.TextField,
    on_send,
    on_add_material=None,
    attachments: ft.Control | None = None,
    voice_button: ft.Control | None = None,
    voice_status: ft.Control | None = None,
    live_button: ft.Control | None = None,
    live_status: ft.Control | None = None,
) -> ft.Container:
    input_row = ft.Row(
        expand=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=8,
        controls=[
            build_add_material_button(on_click=on_add_material),
            prompt,
            voice_button if voice_button is not None else build_microphone_button(),
            *([live_button] if live_button is not None else []),
            build_send_button(on_send),
        ],
    )

    return ft.Container(
        border_radius=10,
        border=ft.Border.all(2, "#00c753"),
        bgcolor="#d9ffe6",
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        content=ft.Column(
            spacing=4,
            controls=[
                attachments or ft.Container(height=0),
                voice_status if voice_status is not None else ft.Container(height=0),
                live_status if live_status is not None else ft.Container(height=0),
                input_row,
            ],
        ),
    )
