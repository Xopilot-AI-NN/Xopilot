"""
Файл: /App/app/chat/composer/buttons/add_material.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Компонент add_material интерфейса Xopilot.
"""
import flet as ft
from ....menu.buttons.brand import brand_button

def build_add_material_button(on_click=None):
    return brand_button(ft.Icons.ADD, 'Добавить материал', on_click)
