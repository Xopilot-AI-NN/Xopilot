import flet as ft
from .brand import brand_button

def build_live_button(on_click=None):
    return brand_button(ft.Icons.GRAPHIC_EQ, 'Live — голосовой разговор', on_click)
