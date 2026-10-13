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
    from .palette import color, outline_color
except ImportError:
    from app.palette import color, outline_color

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
    compact: bool = False,
    viewport_width: float | None = None,
) -> ft.Container:
    add_button = build_add_material_button(on_click=on_add_material)
    voice_button = voice_button if voice_button is not None else build_microphone_button()
    send_button = send_button if send_button is not None else build_send_button(on_send)
    send_button.visible = bool(prompt.value or (attachments is not None and attachments.visible))
    if live_button is not None:
        live_button.visible = not send_button.visible
    input_row = ft.Row(controls=[prompt], vertical_alignment=ft.CrossAxisAlignment.END)
    tools = ft.Container()
    actions = [add_button, voice_button, send_button, *([live_button] if live_button is not None else [])]
    original_sizes = [(button, button.width, button.height, button.border_radius) for button in actions]

    container = ft.Container(
        border_radius=20,
        border=ft.Border.all(2, outline_color()),
        bgcolor=color("#f3fffc"),
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        content=ft.Column(
            spacing=0,
            controls=[
                # Keep child positions stable when a status/panel disappears.
                # Without these shells Flutter remounts the following field
                # when visible children are filtered, losing keyboard focus.
                *[ft.Container(content=control) for control in (attachments, voice_status, live_status, composer_status) if control is not None],
                input_row,
                tools,
            ],
        ),
    )

    layout_mode = None
    short_input = False
    def set_short_input(value):
        nonlocal short_input
        short_input = bool(value and layout_mode)
        # Keep the field under the same parent: moving it to the tools row
        # recreates Flutter's TextField and dismisses the open keyboard.
        prompt.dense = short_input
        prompt.height = 28 if short_input else None
        prompt.content_padding = ft.Padding.symmetric(horizontal=6, vertical=4 if short_input else (10 if layout_mode else 5))
        container.padding = ft.Padding.symmetric(horizontal=8 if layout_mode else 12,
                                                  vertical=2 if short_input else (6 if layout_mode else 10))
        tools.margin = ft.Margin.only(top=0 if short_input else 4)

    def set_compact(value, width=None):
        nonlocal layout_mode
        narrow = value and isinstance(width, (int, float)) and width < 360
        if model_button is not None:
            getattr(model_button, '_xopilot_set_narrow', lambda _: None)(narrow)
        if layout_mode == value:
            return
        layout_mode = value
        # Move the existing controls, preserving recording/sending state and
        # callbacks. No duplicate controls in hidden desktop/mobile subtrees.
        input_row.controls = [prompt]
        prompt.max_lines = 4 if value else 6
        prompt.text_size = 14 if value else None
        prompt.content_padding = ft.Padding.symmetric(horizontal=6, vertical=10 if value else 5)
        container.padding = ft.Padding.symmetric(horizontal=8 if value else 12, vertical=6 if value else 10)
        container.border = ft.Border.all(1 if value else 2, outline_color())
        for button, width, height, radius in original_sizes:
            button.width, button.height = (48, 48) if value else (width, height)
            button.border_radius = 24 if value else radius
        for selector in (model_button, agent_button):
            if selector is not None:
                getattr(selector, '_xopilot_set_compact', lambda _: None)(value)
        if value:
            tools.content = ft.Row(spacing=2, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                add_button, *([model_button] if model_button is not None else []),
                *([agent_button] if agent_button is not None else []), voice_button,
                *([live_button] if live_button is not None else []),
                send_button,
            ])
        else:
            tools.content = ft.Row(spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                add_button, *([model_button] if model_button is not None else []),
                *([agent_button] if agent_button is not None else []), ft.Container(expand=True),
                voice_button, *([live_button] if live_button is not None else []), send_button,
            ])
        set_short_input(short_input)
    container._xopilot_set_compact = set_compact
    container._xopilot_set_short_input = set_short_input
    set_compact(compact, viewport_width)
    return container
