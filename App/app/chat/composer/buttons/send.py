"""
Файл: /App/app/chat/composer/buttons/send.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Компонент send интерфейса Xopilot.
"""
import flet as ft
from ....menu.buttons.brand import brand_button

def build_send_button(on_click=None):
    return brand_button(ft.Icons.SEND_ROUNDED, 'Отправить сообщение', on_click)
