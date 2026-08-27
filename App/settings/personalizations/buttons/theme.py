"""
Файл: /App/settings/personalizations/buttons/theme.py
Описание: Кнопка-переключатель темы оформления.
    Состояние читается/сохраняется в локальной БД (ключ "theme"), переживает перезапуск.
"""

import flet as ft

try:
    from services.db import get_setting, set_setting
except Exception:  # noqa: BLE001 — БД-модуль может быть ещё не собран, UI должен работать без него
    def get_setting(key, default=None):  # type: ignore
        return default

    def set_setting(key, value):  # type: ignore
        return False


def build_theme_switch(page: ft.Page, on_status) -> ft.Switch:
    is_dark = get_setting("theme", "light") == "dark"
    page.theme_mode = ft.ThemeMode.DARK if is_dark else ft.ThemeMode.LIGHT

    switch = ft.Switch(
        value=is_dark,
        active_color="#087f8c",
    )

    def change(_):
        page.theme_mode = ft.ThemeMode.DARK if switch.value else ft.ThemeMode.LIGHT
        set_setting("theme", "dark" if switch.value else "light")
        on_status("Тема применена")
        page.update()

    switch.on_change = change
    return switch