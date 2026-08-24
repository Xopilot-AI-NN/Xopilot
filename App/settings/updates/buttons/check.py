"""
Файл: /App/settings/updates/buttons/check.py
Описание: Кнопка проверки обновлений приложения.
"""

import flet as ft


def build_check_button(on_click) -> ft.FilledButton:
    return ft.FilledButton("Проверить", on_click=on_click)
