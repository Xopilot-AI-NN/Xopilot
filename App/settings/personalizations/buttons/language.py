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
    option_style = ft.ButtonStyle(
        color="#123b43",
        bgcolor={
            ft.ControlState.DEFAULT: "#f5fffc",
            ft.ControlState.HOVERED: "#e3f7f2",
            ft.ControlState.FOCUSED: "#d7f1eb",
        },
        overlay_color=ft.Colors.TRANSPARENT,
        shape=ft.RoundedRectangleBorder(radius=10),
        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
        animation_duration=120,
    )
    select = ft.Dropdown(
        value=saved,
        width=132,
        dense=True,
        filled=True,
        fill_color="#f5fffc",
        bgcolor="#f5fffc",
        hover_color="#edfbf8",
        color="#123b43",
        trailing_icon=ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED,
        selected_trailing_icon=ft.Icons.KEYBOARD_ARROW_UP_ROUNDED,
        border={
            ft.ControlState.DEFAULT: ft.OutlineInputBorder(
                border_radius=12,
                side=ft.BorderSide(color="#a8ddd7"),
            ),
            ft.ControlState.FOCUSED: ft.OutlineInputBorder(
                border_radius=12,
                side=ft.BorderSide(width=2, color="#087f8c"),
            ),
        },
        menu_style=ft.MenuStyle(
            bgcolor="#f5fffc",
            elevation=10,
            shadow_color="#33000000",
            shape=ft.RoundedRectangleBorder(radius=14),
            side=ft.BorderSide(color="#b6e5df", width=1),
            padding=ft.Padding.all(6),
        ),
        expanded_insets=ft.Padding.only(top=6),
        options=[
            ft.DropdownOption(
                key="ru",
                text="Русский",
                leading_icon=ft.Icons.LANGUAGE,
                style=option_style,
            ),
            ft.DropdownOption(
                key="en",
                text="English",
                leading_icon=ft.Icons.LANGUAGE,
                style=option_style,
            ),
        ],
    )

    def change(_):
        set_setting("language", select.value or "ru")
        on_status("Язык сохранён")

    select.on_select = change
    return select