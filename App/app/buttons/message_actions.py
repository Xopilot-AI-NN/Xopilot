"""Compact actions remain accessible with a mouse, keyboard or touch."""
import flet as ft
try:
    from ..palette import color
except ImportError:
    from app.palette import color


def build_message_actions(text, files, on_action, can_edit, message_id=None):
    async def action(name):
        await on_action(name, text, files, message_id)

    async def copy(_):
        await action('copy')

    def item(label, icon, name):
        async def invoke(_):
            await action(name)
        return ft.PopupMenuItem(content=label, icon=icon, on_click=invoke)

    return ft.Row(spacing=0, tight=True, height=24, controls=[
        ft.IconButton(icon=ft.Icons.CONTENT_COPY, icon_color=color('#087f8c'), icon_size=14,
                      width=26, height=24, padding=0, tooltip='Копировать', on_click=copy),
        ft.PopupMenuButton(icon=ft.Icons.MORE_HORIZ, icon_color=color('#087f8c'), icon_size=18,
                           tooltip='Действия сообщения', width=26, height=24, padding=0,
                           items=[item('Ответить', ft.Icons.REPLY, 'reply'),
                                  item('Цитировать', ft.Icons.FORMAT_QUOTE, 'quote'),
                                  *([item('Изменить', ft.Icons.EDIT, 'edit')] if can_edit else []),
                                  item('Удалить', ft.Icons.DELETE_OUTLINE, 'delete')]),
    ])
