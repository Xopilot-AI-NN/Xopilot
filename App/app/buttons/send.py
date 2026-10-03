import flet as ft
from .brand import brand_button

def build_send_button(on_click=None):
    return brand_button(ft.Icons.SEND_ROUNDED, 'Отправить сообщение', on_click)
