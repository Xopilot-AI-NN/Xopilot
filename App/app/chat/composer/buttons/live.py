"""
Файл: /App/app/chat/composer/buttons/live.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Компонент live интерфейса Xopilot.
"""
import flet as ft
from ....menu.buttons.brand import brand_button

def build_live_button(on_click=None):
    return brand_button(ft.Icons.GRAPHIC_EQ, 'Live — голосовой разговор', on_click)
