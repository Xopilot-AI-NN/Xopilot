import flet as ft
from .brand import brand_button

def build_add_material_button(on_click=None):
    return brand_button(ft.Icons.ADD, 'Добавить материал', on_click)
