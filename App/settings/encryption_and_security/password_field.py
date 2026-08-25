"""
Файл: /App/settings/encryption_and_security/password_field.py
Описание: __Поле ввода пароля__.
           Используется для настройки пароля шифрования истории.
"""

import flet as ft


def build_password_field() -> ft.TextField:
    return ft.TextField(
        label="Пароль шифрования",
        password=True,
        can_reveal_password=True,
        width=330,
        disabled=True,
    )
