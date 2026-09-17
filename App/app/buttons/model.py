"""
Файл: App/app/buttons/model.py
Описание: Компактный встроенный выбор модели обычного чата из строки ввода.
"""

from __future__ import annotations

import inspect

import flet as ft

try:
    from ...services.llm import list_local_models
    from ...services.model_settings import get_selected_chat_model, model_display_name
except ImportError:
    from services.llm import list_local_models
    from services.model_settings import get_selected_chat_model, model_display_name


_MENU_BG = "#ecfffa"
_MENU_TEXT = "#123b43"
_MENU_MUTED = "#47747a"
_MENU_ACCENT = "#087f8c"
_MENU_BORDER = "#b6e5df"
_MENU_HOVER = "#ddf8f2"
_SELECTED_BG = "#d8f5ee"


def build_model_button(on_select=None):
    """
    Возвращает встроенный селектор модели для нижней панели.

    В отличие от PopupMenuButton список не рисуется отдельным плавающим окном:
    при открытии блок модели физически увеличивается вверх и остаётся частью
    панели ввода. Если установлена только одна модель, список вообще не
    раскрывается и стрелка скрыта.
    """
    is_open = False
    current_models: list[str] = []

    model_label = ft.Text(
        "Модель",
        size=12,
        color=_MENU_TEXT,
        weight=ft.FontWeight.W_600,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
        expand=True,
    )

    arrow = ft.Icon(
        ft.Icons.KEYBOARD_ARROW_UP_ROUNDED,
        size=18,
        color=_MENU_MUTED,
        visible=False,
    )

    trigger = ft.Container(
        width=95,
        height=48,
        border_radius=24,
        border=ft.Border.all(1, _MENU_BORDER),
        bgcolor=_MENU_BG,
        ink=True,
        ink_color=_MENU_HOVER,
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.only(left=5, right=5),
        tooltip="Выбор модели",
        content=ft.Row(
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=20,
                    height=20,
                    border_radius=10,
                    bgcolor=_SELECTED_BG,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(
                        ft.Icons.SMART_TOY_OUTLINED,
                        size=13,
                        color=_MENU_ACCENT,
                    ),
                ),
                model_label,
                arrow,
            ],
        ),
    )

    menu_list = ft.Column(spacing=2, tight=True, controls=[])
    menu_shell = ft.Container(
        width=190,
        visible=False,
        bgcolor=_MENU_BG,
        border=ft.Border.all(1, _MENU_BORDER),
        border_radius=ft.BorderRadius.only(
            top_left=14,
            top_right=14,
            bottom_left=6,
            bottom_right=6,
        ),
        padding=ft.Padding.all(5),
        margin=ft.Margin.only(bottom=3),
        content=menu_list,
    )

    root = ft.Column(
        width=95,
        spacing=0,
        tight=True,
        horizontal_alignment=ft.CrossAxisAlignment.START,
        controls=[menu_shell, trigger],
    )

    def safe_update():
        try:
            root.update()
        except Exception:
            pass

    def set_open(value: bool, update: bool = True):
        nonlocal is_open
        is_open = bool(value and len(current_models) > 1)
        menu_shell.visible = is_open
        arrow.icon = (
            ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED
            if is_open
            else ft.Icons.KEYBOARD_ARROW_UP_ROUNDED
        )
        # Когда список раскрыт, он визуально продолжает кнопку, а не парит над ней.
        trigger.border_radius = (
            ft.BorderRadius.only(
                top_left=7,
                top_right=7,
                bottom_left=24,
                bottom_right=24,
            )
            if is_open
            else 24
        )
        if update:
            safe_update()

    def toggle_menu(_):
        if len(current_models) <= 1:
            return
        set_open(not is_open)

    trigger.on_click = toggle_menu

    async def choose(filename: str):
        set_open(False, update=False)
        if on_select is not None:
            result = on_select(filename)
            if inspect.isawaitable(result):
                await result
        refresh(update=True)

    def make_handler(filename: str):
        async def handle(_):
            await choose(filename)

        return handle

    def make_row(filename: str, selected: bool) -> ft.Container:
        return ft.Container(
            height=38,
            border_radius=9,
            bgcolor=_SELECTED_BG if selected else _MENU_BG,
            ink=True,
            ink_color=_MENU_HOVER,
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            on_click=make_handler(filename),
            content=ft.Row(
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(
                        ft.Icons.SMART_TOY_OUTLINED,
                        size=13,
                        color=_MENU_ACCENT,
                    ),
                    ft.Text(
                        model_display_name(filename),
                        size=12,
                        color=_MENU_TEXT,
                        weight=ft.FontWeight.W_600 if selected else ft.FontWeight.W_500,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        expand=True,
                    ),
                    ft.Icon(
                        ft.Icons.CHECK_ROUNDED,
                        size=16,
                        color="#08734d",
                        visible=selected,
                    ),
                ],
            ),
        )

    def refresh(update: bool = False):
        nonlocal current_models, is_open
        current_models = list_local_models()
        selected = get_selected_chat_model()

        if selected:
            display = model_display_name(selected)
            model_label.value = display
            trigger.tooltip = (
                f"Модель чата: {display}"
                if len(current_models) <= 1
                else f"Модель чата: {display} · нажмите для выбора"
            )
        else:
            model_label.value = "Нет моделей"
            trigger.tooltip = "Модели не найдены · App/data/models"

        arrow.visible = len(current_models) > 1
        menu_list.controls = [
            make_row(filename, filename == selected)
            for filename in current_models[:5]
        ]

        # Для очень большого каталога не раздуваем нижнюю панель бесконечно.
        # Первые пять моделей остаются компактными; остальные доступны в настройках.
        if len(current_models) > 5:
            menu_list.controls.append(
                ft.Container(
                    height=30,
                    alignment=ft.Alignment.CENTER_LEFT,
                    padding=ft.Padding.only(left=8),
                    content=ft.Text(
                        f"Ещё {len(current_models) - 5} · в настройках",
                        size=10,
                        color=_MENU_MUTED,
                    ),
                )
            )

        if len(current_models) <= 1:
            is_open = False
            menu_shell.visible = False
            trigger.border_radius = 24

        if update:
            safe_update()

    refresh()
    return root, refresh
