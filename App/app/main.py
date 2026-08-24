"""
Файл: /App/app/main.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Окно__
        В котором располагаются элементы интерфейса
"""



import flet as ft
from typing import cast

from .backgraund import build_background_layout
from .chat import build_chat
from .files import build_file_attachments
from .message import build_user_message, messages as build_messages
from .prompt import build_prompt, build_prompt_container
from .menu import build_menu, build_menu_overlay


def build_app_ui(page: ft.Page) -> ft.Control:
    page.padding = 0
    page.bgcolor = "#b3f2ff"

    prompt = build_prompt()
    selected_files = []
    attachment_strip = build_file_attachments(selected_files, lambda _: None)
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    def refresh_attachments():
        rendered = build_file_attachments(selected_files, remove_file)
        attachment_strip.controls = rendered.controls
        attachment_strip.visible = rendered.visible
        attachment_strip.update()

    def remove_file(file):
        if file in selected_files:
            selected_files.remove(file)
            refresh_attachments()

    async def on_add_material(_):
        files = await file_picker.pick_files(
            dialog_title="Выберите материалы",
            allow_multiple=True,
            with_data=False,
        )
        for file in files or []:
            if not any(selected.path == file.path for selected in selected_files):
                selected_files.append(file)
        refresh_attachments()

    def on_send(e):
        text = prompt.value or ""
        if not text.strip() and not selected_files:
            return
        chat_list = cast(ft.ListView, chat.content)
        chat_list.controls.append(build_user_message(text, selected_files.copy()))
        prompt.value = ""
        selected_files.clear()
        refresh_attachments()
        chat_list.update()

    chat_messages = build_messages()
    chat = build_chat(chat_messages)
    prompt_container = build_prompt_container(
        prompt,
        on_send,
        on_add_material=on_add_material,
        attachments=attachment_strip,
    )

    async def handle_menu_toggle(e):
        await toggle_menu()

    menu = build_menu(on_menu_click=handle_menu_toggle)
    menu_overlay, toggle_menu = build_menu_overlay(menu, page)

    return build_background_layout(chat, prompt_container, menu, menu_overlay)