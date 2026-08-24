"""
Файл: /App/settings/personalizations/buttons/theme.py
Описание: Кнопка-переключатель темы оформления.
"""

import flet as ft


def build_theme_switch(page: ft.Page, on_status) -> ft.Switch:
    switch = ft.Switch(
        value=page.theme_mode == ft.ThemeMode.DARK,
        active_color="#087f8c",
    )

    def change(_):
        page.theme_mode = ft.ThemeMode.DARK if switch.value else ft.ThemeMode.LIGHT
        on_status("Тема применена")
        page.update()

    switch.on_change = change
    return switch
