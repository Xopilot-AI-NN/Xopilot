"""
Файл: /App/app/menu.py
Разработчик: DenBroLiik, Claude
Версия: 2.0.0
Описание: __Меню__
        Узкая панель слева от чата:
            сверху  — меню, новый чат, рабочие пространства, чаты
            снизу    — настройки

        build_menu_overlay — та же раскладка (группа сверху +
        настройки снизу, SPACE_BETWEEN), что и в компактном рейле,
        только шире и с подписями. При открытии: компактный рейл
        плавно гаснет (opacity), а поверх него на его же месте
        растёт (animate по width) панель того же стиля — визуально
        полное меню "вырастает" из маленького. При закрытии —
        симметрично в обратную сторону.

        Подписи пунктов сидят в обёртке с собственной анимируемой
        width (0 -> LABEL_WIDTH). Важно: длительность этой анимации
        (PANEL_ANIMATION_MS) СОВПАДАЕТ с длительностью анимации
        ширины самой панели — если бы они были разными, подпись
        "обгоняла" бы рост панели и Flutter кидал overflow-warning
        (та самая красная рамка на кнопке "Новый чат"). При одной
        длительности и кривой доступное место в панели всегда растёт
        быстрее, чем ширина подписи — переполнения не будет.

        Кнопки рейла — динамические: при изменении ширины рейла
        (size_change_interval/on_size_change) считается ratio (0..1)
        между RAIL_WIDTH_MIN и RAIL_WIDTH_MAX — это единственное,
        что принадлежит самому рейлу-контейнеру. Пересчёт размера
        кнопки/иконки по этому ratio делает уже сама кнопка
        (resize_*_button в buttons/*.py).
"""

import asyncio
import flet as ft
import platform

from .buttons.menu import build_menu_button, resize_menu_button
from .buttons.new_chat import build_new_chat_button, resize_new_chat_button
from .buttons.settings import build_settings_button, resize_settings_button
from .buttons.workspaces import build_workspaces_button, resize_workspaces_button
from .buttons.chats import build_chats_button, resize_chats_button

RAIL_WIDTH_DEFAULT = 90 if platform.system() != "Windows" else 64
RAIL_WIDTH_MIN = 32
RAIL_WIDTH_MAX = 130
PANEL_WIDTH = 280
PANEL_ANIMATION_MS = 220
LABEL_WIDTH = 170


def build_menu(
    on_menu_click=None,
    on_new_chat_click=None,
    on_workspaces_click=None,
    on_chats_click=None,
    on_settings_click=None,
) -> ft.Container:
    menu_btn = build_menu_button(on_click=on_menu_click)
    new_chat_btn = build_new_chat_button(on_click=on_new_chat_click)
    workspaces_btn = build_workspaces_button(on_click=on_workspaces_click)
    chats_btn = build_chats_button(on_click=on_chats_click)
    settings_btn = build_settings_button(on_click=on_settings_click)

    def handle_resize(e):
        span = max(RAIL_WIDTH_MAX - RAIL_WIDTH_MIN, 1)
        ratio = (e.width - RAIL_WIDTH_MIN) / span
        resize_menu_button(menu_btn, ratio)
        resize_new_chat_button(new_chat_btn, ratio)
        resize_workspaces_button(workspaces_btn, ratio)
        resize_chats_button(chats_btn, ratio)
        resize_settings_button(settings_btn, ratio)

    return ft.Container(
        width=RAIL_WIDTH_DEFAULT,
        bgcolor="#e6ffffff",
        blur=14,
        border_radius=8,
        border=ft.border.Border.all(2, "#d9ffe6"),
        padding=ft.padding.Padding.symmetric(horizontal=1, vertical=8),
        opacity=1,
        animate_opacity=200,
        size_change_interval=80,
        on_size_change=handle_resize,
        content=ft.Column(
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[menu_btn, new_chat_btn, workspaces_btn, chats_btn],
                ),
                settings_btn,
            ],
        ),
    )


def _overlay_item(
    icon, label: str, on_click=None
) -> tuple[ft.Container, ft.Container, ft.Text]:
    label_text = ft.Text(
        label,
        font_family="Google Sans",
        color=ft.Colors.BLACK,
        size=14,
        no_wrap=True,
        opacity=0,
        animate_opacity=PANEL_ANIMATION_MS,
    )

    label_wrapper = ft.Container(
        width=0,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        animate=ft.Animation(
            duration=PANEL_ANIMATION_MS, curve=ft.AnimationCurve.EASE_OUT
        ),
        content=label_text,
    )

    row = ft.Container(
        border_radius=10,
        padding=ft.padding.Padding.symmetric(horizontal=8, vertical=8),
        bgcolor=ft.Colors.TRANSPARENT,
        ink=True,
        animate=ft.Animation(duration=150, curve=ft.AnimationCurve.EASE_OUT),
        on_click=on_click,
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            controls=[
                ft.Container(
                    width=30,
                    height=30,
                    border_radius=15,
                    bgcolor="#ff6666ff",
                    alignment=ft.alignment.Alignment.CENTER,
                    content=ft.Icon(icon, color=ft.Colors.WHITE, size=15),
                ),
                label_wrapper,
            ],
        ),
    )

    def handle_hover(e: ft.Event[ft.Container]):
        e.control.bgcolor = "#1aff6666" if e.data else ft.Colors.TRANSPARENT
        e.control.update()

    row.on_hover = handle_hover
    # Возвращаем сам Text, чтобы не лезть в Optional-поле .content
    return row, label_wrapper, label_text


def build_menu_overlay(rail: ft.Container, page: ft.Page):
    is_open = False

    new_chat_row, new_chat_wrapper, new_chat_text = _overlay_item(
        ft.Icons.ADD_COMMENT, "Новый чат"
    )
    workspaces_row, workspaces_wrapper, workspaces_text = _overlay_item(
        ft.Icons.WORKSPACES, "Пространства"
    )
    chats_row, chats_wrapper, chats_text = _overlay_item(
        ft.Icons.CHAT_BUBBLE_OUTLINE, "Чаты"
    )
    settings_row, settings_wrapper, settings_text = _overlay_item(
        ft.Icons.SETTINGS, "Настройки"
    )

    wrappers = (
        new_chat_wrapper,
        workspaces_wrapper,
        chats_wrapper,
        settings_wrapper,
    )
    texts = (new_chat_text, workspaces_text, chats_text, settings_text)

    panel = ft.Container(
        width=RAIL_WIDTH_DEFAULT,
        top=0,
        bottom=0,
        left=0,
        bgcolor="#e6ffffff",
        blur=14,
        border_radius=ft.border_radius.BorderRadius.only(
            top_right=16, bottom_right=16
        ),
        border=ft.border.Border.all(2, "#d9ffe6"),
        padding=ft.padding.Padding.symmetric(horizontal=6, vertical=8),
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        animate=ft.Animation(
            duration=PANEL_ANIMATION_MS, curve=ft.AnimationCurve.EASE_OUT
        ),
        content=ft.Column(
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[new_chat_row, workspaces_row, chats_row],
                ),
                settings_row,
            ],
        ),
    )

    async def toggle():
        nonlocal is_open
        is_open = not is_open

        if is_open:
            overlay_stack.visible = True
            rail.opacity = 0
            page.update()
            await asyncio.sleep(0.02)
            panel.width = PANEL_WIDTH
            for wrapper in wrappers:
                wrapper.width = LABEL_WIDTH
            for text in texts:
                text.opacity = 1          # <- теперь тип точно ft.Text
            page.update()
        else:
            panel.width = RAIL_WIDTH_DEFAULT
            for wrapper in wrappers:
                wrapper.width = 0
            for text in texts:
                text.opacity = 0          # <- и здесь тоже
            page.update()
            await asyncio.sleep(PANEL_ANIMATION_MS / 1000)
            overlay_stack.visible = False
            rail.opacity = 1
            page.update()

    async def handle_new_chat_click(_):
        # TODO: сбросить историю чата / создать новый диалог
        await toggle()

    async def handle_scrim_click(_):
        await toggle()

    new_chat_row.on_click = handle_new_chat_click

    scrim = ft.Container(
        expand=True,
        bgcolor="#40000000",
        blur=5,
        on_click=handle_scrim_click,
    )

    overlay_stack = ft.Stack(
        expand=True,
        visible=False,
        controls=[scrim, panel],
    )

    return overlay_stack, toggle