"""Кнопки действий сообщения."""

import flet as ft


def build_message_actions(
    text: str,
    files: list[ft.FilePickerFile] | None,
    on_action,
    can_edit: bool,
    message_id: int | None = None,
) -> ft.Row:
    async def handle_action(action: str):
        await on_action(action, text, files, message_id)

    async def on_copy(_):
        await handle_action("copy")

    async def on_reply(_):
        await handle_action("reply")

    async def on_quote(_):
        await handle_action("quote")

    async def on_edit(_):
        await handle_action("edit")

    controls: list[ft.Control] = [
        ft.IconButton(
            icon=ft.Icons.CONTENT_COPY,
            icon_color="#087f8c",
            icon_size=15,
            width=28,
            height=28,
            padding=0,
            bgcolor="#dff8f3",
            hover_color="#bcefe5",
            tooltip="Копировать",
            on_click=on_copy,
        ),
        ft.IconButton(
            icon=ft.Icons.REPLY,
            icon_color="#087f8c",
            icon_size=15,
            width=28,
            height=28,
            padding=0,
            bgcolor="#dff8f3",
            hover_color="#bcefe5",
            tooltip="Ответить",
            on_click=on_reply,
        ),
        ft.IconButton(
            icon=ft.Icons.FORMAT_QUOTE,
            icon_color="#087f8c",
            icon_size=15,
            width=28,
            height=28,
            padding=0,
            bgcolor="#dff8f3",
            hover_color="#bcefe5",
            tooltip="Цитировать",
            on_click=on_quote,
        ),
    ]
    if can_edit:
        controls.append(
            ft.IconButton(
                icon=ft.Icons.EDIT,
                icon_color="#087f8c",
                icon_size=15,
                width=28,
                height=28,
                padding=0,
                bgcolor="#dff8f3",
                hover_color="#bcefe5",
                tooltip="Изменить",
                on_click=on_edit,
            )
        )
    return ft.Row(spacing=2, tight=True, height=28, controls=controls)
