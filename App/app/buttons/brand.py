"""Shared menu-style actions; callers retain their button state and callbacks."""
import flet as ft
from ..palette import outline_color
try:
    from ...services.platforms import is_android
except ImportError:
    from services.platforms import is_android

def brand_gradient():
    return ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                             colors=['#00d6a3', '#08a9d9', '#7657ff'])

def brand_button(icon, tooltip, on_click=None, size=40):
    if is_android():
        size = max(48, size)
    button = ft.Container(width=size, height=size, border_radius=size/2,
        border=ft.Border.all(2, outline_color()), gradient=brand_gradient(),
        alignment=ft.Alignment.CENTER, ink=True, tooltip=tooltip,
        content=ft.Icon(icon, color=ft.Colors.WHITE, size=20), on_click=on_click)
    button._xopilot_fixed_colors = True
    return button
