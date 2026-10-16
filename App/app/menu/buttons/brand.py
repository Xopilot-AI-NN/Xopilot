"""
Файл: /App/app/menu/buttons/brand.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Тональные кнопки Xopilot с мягким градиентом и геометрией Material 3.
"""
import flet as ft
from ...theme.palette import is_dark_theme
from ...theme.button_colors import action_role, button_tones
try:
    from ....services.platforms import is_android
except ImportError:
    from services.platforms import is_android


def brand_gradient(role='ai'):
    tones, _, _ = button_tones(role, is_dark_theme())
    return ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                             colors=list(tones))


def style_brand_button(button, role):
    tones, ink, outline = button_tones(role, is_dark_theme())
    button._xopilot_button_role = role
    button._xopilot_fixed_colors = True
    button.bgcolor = None
    button.gradient = brand_gradient(role)
    button.border = ft.Border.all(1, outline)
    button.ink_color = ft.Colors.with_opacity(.10, ink)
    def foreground(control):
        if isinstance(control, (ft.Icon, ft.Text)):
            control.color = ink
        elif isinstance(control, ft.IconButton):
            control.icon_color = ink
        for child in getattr(control, 'controls', None) or []:
            foreground(child)
        child = getattr(control, 'content', None)
        if isinstance(child, ft.Control):
            foreground(child)
    if button.content is not None:
        foreground(button.content)
    return button


def brand_button(icon, tooltip, on_click=None, size=40):
    if is_android():
        size = max(48, size)
    button = ft.Container(width=size, height=size, border_radius=min(18,size*.4),
        alignment=ft.Alignment.CENTER, ink=True, tooltip=tooltip,
        content=ft.Icon(icon, size=20), on_click=on_click)
    return style_brand_button(button, action_role(icon, tooltip))
