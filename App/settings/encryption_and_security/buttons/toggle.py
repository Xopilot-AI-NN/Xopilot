"""
Файл: /App/settings/encryption_and_security/buttons/toggle.py
Описание: Кнопка-переключатель шифрования истории.
"""

import flet as ft


def build_encryption_toggle(on_change) -> ft.Switch:
    switch = ft.Switch(value=False, active_color="#087f8c")
    switch.on_change = on_change
    return switch
