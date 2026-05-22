"""
Файл: /App/encryption/chat.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Чат__
        клеится по середине выше строки для ввода в окне
"""


import flet as ft

def get_chat_component():
    return ft.ListView(
        expand=True,
        spacing=10,
        auto_scroll=True,
        padding=10
    )
