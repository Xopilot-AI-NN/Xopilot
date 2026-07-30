"""
Файл: /App/app/menu.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Меню__
        Узкая панель слева от чата:
            сверху  — меню, рабочие пространства, чаты
            снизу    — настройки

        Кнопка меню открывает выезжающую панель (build_menu_overlay) —
        это единственный файл для всей логики меню, без отдельного
        menu_overlay.py — чтобы не было двух разных "меню" в проекте.
        Панель полупрозрачная/размытая, узкая (не полэкрана!),
        пункты выровнены по левому краю.

        Рейл и панель используют один и тот же стеклянный стиль
        (bgcolor "#e6ffffff" + blur), как и пузыри сообщений — единая
        стеклянная палитра Material 3 Expressive по всему интерфейсу.
"""


import flet as ft
import platform

from .buttons.menu import build_menu_button
from .buttons.settings import build_settings_button
from .buttons.workspaces import build_workspaces_button
from .buttons.chats import build_chats_button


def build_menu(
    on_menu_click=None,
    on_workspaces_click=None,
    on_chats_click=None,
    on_settings_click=None,
) -> ft.Container:
    return ft.Container(
        width=54 if platform.system() != "Windows" else 35,
        bgcolor="#e6ffffff",
        blur=14,
        border_radius=8,
        border=ft.border.Border.all(2, "#d9ffe6"),
        padding=ft.padding.Padding.symmetric(horizontal=1, vertical=8),
        content=ft.Column(
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        build_menu_button(on_click=on_menu_click),
                        build_workspaces_button(on_click=on_workspaces_click),
                        build_chats_button(on_click=on_chats_click),
                    ],
                ),
                build_settings_button(on_click=on_settings_click),
            ],
        ),
    )


def _menu_item(icon, label: str, on_click=None) -> ft.Container:
    return ft.Container(
        border_radius=10,
        padding=ft.padding.Padding.symmetric(horizontal=12, vertical=10),
        ink=True,
        on_click=on_click,
        content=ft.Row(
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.Icon(icon, color=ft.Colors.BLACK, size=28 if platform.system() != "Windows" else 18),
                ft.Text(
                    label,
                    font_family="Google Sans",
                    color=ft.Colors.BLACK,
                    size=14,
                ),
            ],
        ),
    )


def build_menu_overlay(on_close=None) -> ft.Stack:
    PANEL_WIDTH = 280

    scrim = ft.Container(
        expand=True,
        bgcolor="#40000000",
        blur=5,
        on_click=on_close,
    )

    panel = ft.Container(
        width=PANEL_WIDTH,
        top=0,
        bottom=0,
        left=0,
        bgcolor="#e6ffffff",
        blur=14,
        border_radius=ft.border_radius.BorderRadius.only(top_right=16, bottom_right=16),
        border=ft.border.Border.all(2, "#d9ffe6"),
        padding=ft.padding.Padding.symmetric(horizontal=8, vertical=16),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            spacing=4,
            controls=[
                ft.Container(
                    padding=ft.padding.Padding.only(left=12, bottom=12),
                    content=ft.Text(
                        "Меню",
                        font_family="Google Sans",
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.BLACK,
                        size=16,
                    ),
                ),
                _menu_item(ft.Icons.ADD_COMMENT, "Новый чат"),
                _menu_item(ft.Icons.WORKSPACES, "Пространства"),
                _menu_item(ft.Icons.HISTORY, "История"),
                _menu_item(ft.Icons.SETTINGS, "Настройки"),
            ],
        ),
    )

    return ft.Stack(
        expand=True,
        visible=False,
        controls=[scrim, panel],
    )