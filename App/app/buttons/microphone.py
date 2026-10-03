import flet as ft
from .brand import brand_button

def build_microphone_button(on_click=None):
    return brand_button(ft.Icons.MIC, 'Диктовка', on_click)
