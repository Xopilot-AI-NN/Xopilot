"""
Файл: /App/app/chat/composer/buttons/microphone.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Компонент microphone интерфейса Xopilot.
"""
import flet as ft
from ....menu.buttons.brand import brand_button

def build_microphone_button(on_click=None):
    return brand_button(ft.Icons.MIC, 'Диктовка', on_click)
