"""
Файл: /App/app/main.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Окно__
        В котором располагаются элементы интерфейса
"""



import flet as ft

from .backgraund import build_background_layout
from .chat import build_chat
from .message import messages as build_messages
from .prompt import build_prompt, build_prompt_container
from .menu import build_menu, build_menu_overlay


def build_app_ui(page: ft.Page) -> ft.Control:
    page.padding = 0
    page.bgcolor = "#b3f2ff"

    prompt = build_prompt()

    def on_send(e):
        text = prompt.value or ""
        # TODO: отправка сообщения в AI

    chat_messages = build_messages()
    prompt_container = build_prompt_container(prompt, on_send)
    chat = build_chat(chat_messages)

    def toggle_menu(_):
        menu_overlay.visible = not menu_overlay.visible
        page.update()

    def close_menu(_):
        menu_overlay.visible = False
        page.update()

    menu_overlay = build_menu_overlay(on_close=close_menu)

    menu = build_menu(on_menu_click=toggle_menu)

    return build_background_layout(chat, prompt_container, menu, menu_overlay)