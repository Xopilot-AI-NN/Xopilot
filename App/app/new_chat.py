"""Explicit destination for a new conversation opened from a project."""
import flet as ft
from .palette import color


def choose_chat_scope(page, workspace, on_choose):
    def choose(identifier):
        page.pop_dialog()
        on_choose(identifier)
    page.show_dialog(ft.AlertDialog(
        title=ft.Text('Где создать чат?'), bgcolor=color('#eafffa'),
        content=ft.Column(tight=True, width=min(380, max(220, (page.width or 500)-112)), spacing=14, controls=[
            ft.Text('Чат проекта использует его инструкции и материалы. Обычный чат работает отдельно.',
                    size=13, color=color('#47747a')),
            ft.FilledButton(content='В проекте «'+workspace['name']+'»', icon=ft.Icons.FOLDER_OUTLINED,
                            on_click=lambda _: choose(workspace['id'])),
            ft.OutlinedButton(content='Обычный чат', icon=ft.Icons.ADD_COMMENT_OUTLINED,
                              on_click=lambda _: choose('all'))]),
        actions=[ft.TextButton(content='Отмена', on_click=lambda _: page.pop_dialog())]))
