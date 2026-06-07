"""
Файл: /App/encryption/main.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Окно__ шифрования при запуске Xopilot.
           Пользователь выбирает — шифровать историю или нет.
           При включённом шифровании требует ввод пароля пользователя
           linux или пароль учётной записи Microsoft на windows.
"""



import flet as ft

from .backgraund import build_background_layout
from .message import build_initial_messages
from .chat import build_chat
from .prompt import build_prompt, build_prompt_container
# from .buttons.disabled import build_close_button


def build_encryption_ui(page: ft.Page) -> ft.Control:
    page.padding = 0
    page.bgcolor = "#b3f2ff"

    prompt = build_prompt()

    def on_send(e):
        password = prompt.data or ""
        # TODO: проверка пароля

    # def on_close(e):
    #     page.window.close()

    messages = build_initial_messages()
    prompt_container = build_prompt_container(prompt, on_send)
    chat = build_chat(messages)

    return build_background_layout(chat, prompt_container)
