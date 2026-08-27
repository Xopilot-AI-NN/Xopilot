"""
Файл: /App/settings/personalizations/buttons/language.py
Описание: Кнопка выбора языка интерфейса.
    Значение читается/сохраняется в локальной БД (ключ "language"), переживает перезапуск.
    Сам перевод интерфейса (i18n) ещё не реализован — только хранение выбора.
"""

import flet as ft

try:
    from services.db import get_setting, set_setting
except Exception:  # noqa: BLE001 — БД-модуль может быть ещё не собран, UI должен работать без него
    def get_setting(key, default=None):  # type: ignore
        return default

    def set_setting(key, value):  # type: ignore
        return False


def build_language_select(on_status) -> ft.Dropdown:
    saved = get_setting("language", "ru")
    select = ft.Dropdown(
        value=saved,
        width=122,
        dense=True,
        options=[
            ft.DropdownOption(key="ru", text="Русский"),
            ft.DropdownOption(key="en", text="English"),
        ],
    )

    def change(_):
        set_setting("language", select.value or "ru")
        on_status("Язык сохранён")

    select.on_select = change
    return select