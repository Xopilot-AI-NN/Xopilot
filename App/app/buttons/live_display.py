"""
Файл: /App/app/buttons/live_display.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __кнопка голосового разговора Live Display__
        клеится в строке для доп функций
"""


import flet as ft
from .brand import brand_button
try:
    from ..palette import color
except ImportError:
    from app.palette import color


def build_live_display_button(on_click=None, active: bool = False) -> ft.Container:
    return brand_button(ft.Icons.SCREEN_SHARE_OUTLINED, "Показать экран", on_click, size=46)
