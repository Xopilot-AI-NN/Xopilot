"""
Файл: /App/settings/personalizations/buttons/language.py
Описание: Предпочтительный язык ответов ИИ.
    Значение читается/сохраняется в локальной БД (ключ "language"), переживает перезапуск.
    Интерфейс остаётся русским; выбор применяется к следующим ответам модели.
"""

import flet as ft
try:
    from ....app.palette import color
except ImportError:
    from app.palette import color

try:
    from ....services.db import get_setting, get_db
except ImportError:
    from services.db import get_setting, get_db


def build_language_select(on_status) -> ft.Dropdown:
    saved = get_setting("response_language", "ru")
    option_style = ft.ButtonStyle(
        color=color("#123b43"),
        bgcolor={
            ft.ControlState.DEFAULT: color("#f5fffc"),
            ft.ControlState.HOVERED: color("#e3f7f2"),
            ft.ControlState.FOCUSED: color("#d7f1eb"),
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
        fill_color=color("#f5fffc"),
        bgcolor=color("#f5fffc"),
        hover_color=color("#edfbf8"),
        color=color("#123b43"),
        trailing_icon=ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED,
        selected_trailing_icon=ft.Icons.KEYBOARD_ARROW_UP_ROUNDED,
        border={
            ft.ControlState.DEFAULT: ft.OutlineInputBorder(
                border_radius=12,
                side=ft.BorderSide(color=color("#a8ddd7")),
            ),
            ft.ControlState.FOCUSED: ft.OutlineInputBorder(
                border_radius=12,
                side=ft.BorderSide(width=2, color=color("#087f8c")),
            ),
        },
        menu_style=ft.MenuStyle(
            bgcolor=color("#f5fffc"),
            elevation=10,
            shadow_color=color("#33000000"),
            shape=ft.RoundedRectangleBorder(radius=14),
            side=ft.BorderSide(color=color("#b6e5df"), width=1),
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
        try:
            get_db().set_setting("response_language", select.value or "ru")
        except Exception as exc:
            select.value = get_setting("response_language", "ru")
            on_status(f"Не удалось сохранить язык: {exc}")
            return
        on_status("Язык ответов сохранён")

    select.on_select = change
    return select
