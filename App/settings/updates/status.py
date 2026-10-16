"""
Файл: /App/settings/updates/status.py
Описание: __Статус обновлений__.
           Отображает версию приложения и результат последней проверки.
"""

import flet as ft
try:
    from ...app.theme.palette import color
except ImportError:
    from app.theme.palette import color


def build_update_status() -> ft.Text:
    return ft.Text("Версия 2.0.0 · проверка не запускалась", size=11, color=color("#47747a"))
