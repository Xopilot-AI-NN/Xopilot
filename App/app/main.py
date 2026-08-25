"""
Файл: /App/app/main.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Окно__
        В котором располагаются элементы интерфейса
"""



import flet as ft
import asyncio
import platform
from typing import cast

from .backgraund import build_background_layout
from .chat import build_chat
from .material import build_file_attachments, file_from_path
from .message import build_user_message, messages as build_messages
from .prompt import build_prompt, build_prompt_container
from .menu import build_menu, build_menu_overlay
from .chats import build_chats_dialog
from .workspace_browser import build_workspaces_dialog
try:
    from ..settings.main import build_settings_dialog
except ImportError:
    from settings.main import build_settings_dialog


def build_app_ui(page: ft.Page) -> ft.Control:
    page.padding = 0
    page.bgcolor = "#b3f2ff"

    prompt = build_prompt()
    selected_files = []
    chat_items = [
        ("Продолжение оформления", "Сегодня · 12 сообщений", True),
        ("Идеи для локального ИИ", "Вчера · 8 сообщений", False),
        ("Материалы проекта Xopilot", "18 февраля · 24 сообщения", False),
        ("Настройка интерфейса", "12 февраля · 16 сообщений", False),
    ]
    workspace_items = [
        ("Xopilot", "Основной проект", ft.Icons.AUTO_AWESOME),
        ("Локальный ИИ", "Модели и эксперименты", ft.Icons.SMART_TOY_OUTLINED),
        ("Дизайн приложения", "Макеты и материалы", ft.Icons.PALETTE_OUTLINED),
    ]
    editing_message = None
    attachment_strip = build_file_attachments(selected_files, lambda _: None)
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    async def refresh_attachments(animated: bool = False):
        rendered = build_file_attachments(selected_files, remove_file)
        attachment_strip.controls = rendered.controls
        attachment_strip.visible = rendered.visible
        if animated and selected_files:
            attachment_strip.opacity = 0
            attachment_strip.update()
            await asyncio.sleep(0.02)
            attachment_strip.opacity = 1
        attachment_strip.update()

    def remove_file(file):
        if file in selected_files:
            selected_files.remove(file)
            page.run_task(refresh_attachments)

    async def on_add_material(_):
        files = await file_picker.pick_files(
            dialog_title="Выберите материалы",
            allow_multiple=True,
            with_data=False,
        )
        for file in files or []:
            if not any(selected.path == file.path for selected in selected_files):
                selected_files.append(file)
        await refresh_attachments(animated=True)

    async def paste_files():
        for path in await page.clipboard.get_files():
            file = file_from_path(path)
            if file and not any(selected.path == file.path for selected in selected_files):
                selected_files.append(file)
        await refresh_attachments(animated=True)

    async def handle_keyboard(e: ft.KeyboardEvent):
        if e.ctrl and e.key.lower() == "v":
            await paste_files()
        elif e.key.lower() == "enter" and not e.shift:
            await on_send(e)

    page.on_keyboard_event = handle_keyboard

    async def handle_message_action(action, text, files):
        nonlocal editing_message
        if action == "copy":
            await page.clipboard.set(text)
        elif action == "reply":
            prompt.value = f"Ответ на сообщение:\n{text}\n\n"
            await prompt.focus()
        elif action == "quote":
            quoted_text = "\n".join(f"> {line}" for line in text.splitlines())
            prompt.value = f"{quoted_text}\n\n"
            await prompt.focus()
        elif action == "edit":
            editing_message = (text, files or [])
            prompt.value = text
            await prompt.focus()
        prompt.update()

    async def on_send(e):
        nonlocal editing_message
        text = prompt.value or ""
        if not text.strip() and not selected_files:
            return
        chat_list = cast(ft.ListView, chat.content)
        if editing_message is not None:
            original_text, original_files = editing_message
            for index, control in enumerate(chat_list.controls):
                if getattr(control, "data", None) == original_text:
                    chat_list.controls[index] = build_user_message(
                        text,
                        original_files,
                        on_action=handle_message_action,
                    )
                    break
            editing_message = None
        else:
            message = build_user_message(
                text,
                selected_files.copy(),
                on_action=handle_message_action,
            )
            message.data = text
            chat_list.controls.append(message)
            chat_items.insert(0, (text[:32] or "Новый чат", "Только что · 1 сообщение", True))
        prompt.value = ""
        selected_files.clear()
        prompt.update()
        page.run_task(refresh_attachments)
        chat_list.update()
        await asyncio.sleep(0.08)
        await chat_list.scroll_to(offset=-1, duration=250)

    chat_messages = build_messages(on_action=handle_message_action)
    chat = build_chat(chat_messages)
    prompt_container = build_prompt_container(
        prompt,
        on_send,
        on_add_material=on_add_material,
        attachments=attachment_strip,
    )

    async def handle_menu_toggle(e):
        await toggle_menu()

    def open_settings(_):
        page.show_dialog(build_settings_dialog(page, cast(ft.ListView, chat.content)))

    def open_chats(_):
        page.show_dialog(build_chats_dialog(page, cast(ft.ListView, chat.content), chat_items))

    def open_workspaces(_):
        page.show_dialog(build_workspaces_dialog(page, workspace_items))

    menu = build_menu(
        on_menu_click=handle_menu_toggle,
        on_settings_click=open_settings,
        on_chats_click=open_chats,
        on_workspaces_click=open_workspaces,
    )
    menu_overlay, toggle_menu = build_menu_overlay(
        menu,
        page,
        on_settings_click=open_settings,
        on_chats_click=open_chats,
        on_workspaces_click=open_workspaces,
    )

    async def scroll_chat_to_bottom():
        await asyncio.sleep(0.15)
        await cast(ft.ListView, chat.content).scroll_to(offset=-1)

    page.run_task(scroll_chat_to_bottom)

    return build_background_layout(chat, prompt_container, menu, menu_overlay)