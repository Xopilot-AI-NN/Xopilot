"""
Файл: /App/app/voice/buttons/live_camera.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __кнопка голосового разговора Live Camera__
        клеится в строке для доп функций
"""


import flet as ft
from ...menu.buttons.brand import brand_button
try:
    from ...theme.palette import color
except ImportError:
    from app.theme.palette import color


def build_live_camera_button(on_click=None, active: bool = False) -> ft.Container:
    return brand_button(ft.Icons.VIDEOCAM_OUTLINED, "Включить камеру", on_click, size=46)
