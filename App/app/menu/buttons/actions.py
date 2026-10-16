"""
Файл: /App/app/menu/buttons/actions.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Компонент actions интерфейса Xopilot.
"""
"""Consistent, touch-friendly actions for account dialogs."""
import flet as ft
from ...theme.palette import color, outline_color


def action_button(label, *, on_click=None, icon=None, secondary=False, disabled=False):
    return ft.FilledButton(
        content=label, icon=icon, on_click=on_click, disabled=disabled, height=48,
        style=ft.ButtonStyle(
            color={ft.ControlState.DEFAULT: color('#123b43') if secondary else ft.Colors.WHITE,
                   ft.ControlState.DISABLED: color('#47747a')},
            bgcolor={ft.ControlState.DEFAULT: color('#dff8f3') if secondary else '#006b78',
                     ft.ControlState.DISABLED: color('#edfbf8')},
            side=ft.BorderSide(1, color('#a8ddd7') if secondary else outline_color()),
            shape=ft.RoundedRectangleBorder(radius=16),
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        ),
    )
