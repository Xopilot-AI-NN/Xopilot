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
try:
    from .palette import color
except ImportError:
    from app.palette import color

from .buttons.add_material import build_add_material_button
from .buttons.microphone import build_microphone_button
from .buttons.send import build_send_button


def build_prompt(on_submit=None) -> ft.TextField:
    field = ft.TextField(
        on_submit=on_submit,
        hint_text="Напишите сообщение…",
        multiline=True,
        shift_enter=True,
        min_lines=1,
        max_lines=6,
        # Flet 1.x: borderless filled field. The visible outline belongs to
        # build_prompt_container(), not to TextField itself.
        filled=True,
        bgcolor=color("#f3fffc"),
        focused_bgcolor=color("#f3fffc"),
        border={state: ft.NoInputBorder() for state in (ft.ControlState.DEFAULT, ft.ControlState.FOCUSED, ft.ControlState.DISABLED, ft.ControlState.ERROR)},
        color=color("#000000"),
        cursor_color=color("#000000"),
        content_padding=ft.Padding.symmetric(horizontal=6, vertical=5),
        expand=True,
    )
    field.__dict__['_xopilot_borderless'] = True
    return field


def build_prompt_container(
    prompt: ft.TextField,
    on_send,
    on_add_material=None,
    attachments: ft.Control | None = None,
    model_button: ft.Control | None = None,
    voice_button: ft.Control | None = None,
    voice_status: ft.Control | None = None,
    live_button: ft.Control | None = None,
    live_status: ft.Control | None = None,
    send_button: ft.Control | None = None,
    composer_status: ft.Control | None = None,
    agent_button: ft.Control | None = None,
) -> ft.Container:
    # Text gets its own row; tools no longer squeeze the draft in narrow windows.
    input_row = ft.Row(controls=[prompt], vertical_alignment=ft.CrossAxisAlignment.END)
    tools = ft.ResponsiveRow(
        spacing=8, run_spacing=6,
        controls=[
            ft.Container(col={"xs": 12, "sm": 6}, content=ft.Row(spacing=6, wrap=True, controls=[
                build_add_material_button(on_click=on_add_material),
                *([model_button] if model_button is not None else []),
                *([agent_button] if agent_button is not None else []),
            ])),
            ft.Container(col={"xs": 12, "sm": 6}, content=ft.Row(
                spacing=6, alignment=ft.MainAxisAlignment.END, controls=[
                    voice_button if voice_button is not None else build_microphone_button(),
                    *([live_button] if live_button is not None else []),
                    send_button if send_button is not None else build_send_button(on_send),
                ],
            )),
        ],
    )

    return ft.Container(
        border_radius=20,
        border=ft.Border.all(2, ft.Colors.WHITE),
        bgcolor=color("#f3fffc"),
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        content=ft.Column(
            spacing=4,
            controls=[
                attachments or ft.Container(height=0),
                voice_status if voice_status is not None else ft.Container(height=0),
                live_status if live_status is not None else ft.Container(height=0),
                composer_status if composer_status is not None else ft.Container(height=0),
                input_row,
                tools,
            ],
        ),
    )
