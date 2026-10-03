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
        "обгоняла" бы рост панели и Flutter кидал бы overflow-warning
        (та самая красная рамка на кнопке "Новый чат"). При одной
        длительности и кривой доступное место в панели всегда растёт
        быстрее, чем ширина подписи — переполнения не будет.

        Кнопки рейла — динамические: при изменении ширины рейла
        (size_change_interval/on_size_change) считается ratio (0..1)
        между RAIL_WIDTH_MIN и RAIL_WIDTH_MAX — это единственное, что
        принадлежит самому рейлу-контейнеру. Пересчёт размера
        кнопки/иконки по этому ratio делает уже сама кнопка
        (resize_*_button в buttons/*.py).
"""

import asyncio
import flet as ft
try:
    from .palette import color
except ImportError:
    from app.palette import color
import platform

from .buttons.account import build_account_button, resize_account_button
from .buttons.menu import build_menu_button, resize_menu_button
from .buttons.new_chat import build_new_chat_button, resize_new_chat_button
from .buttons.settings import build_settings_button, resize_settings_button
from .buttons.workspaces import build_workspaces_button, resize_workspaces_button
from .buttons.chats import build_chats_button, resize_chats_button

RAIL_WIDTH_DEFAULT = 76 if platform.system() != "Windows" else 70
RAIL_WIDTH_MIN = 56
RAIL_WIDTH_MAX = 100
PANEL_WIDTH = 280
PANEL_ANIMATION_MS = 220
LABEL_WIDTH = 170

BRAND_GRADIENT = ft.LinearGradient(
    begin=ft.Alignment.TOP_LEFT,
    end=ft.Alignment.BOTTOM_RIGHT,
    colors=[color("#00D6A3"), color("#08A9D9"), color("#7657FF")],
)


def build_menu(
    on_menu_click=None,
    on_new_chat_click=None,
    on_workspaces_click=None,
    on_chats_click=None,
    on_settings_click=None,
    on_account_click=None,
) -> ft.Container:
    menu_btn = build_menu_button(on_click=on_menu_click, size=50, icon_size=26)
    new_chat_btn = build_new_chat_button(
        on_click=on_new_chat_click, size=50, icon_size=26
    )
    workspaces_btn = build_workspaces_button(
        on_click=on_workspaces_click, size=50, icon_size=26
    )
    chats_btn = build_chats_button(on_click=on_chats_click, size=50, icon_size=26)
    settings_btn = build_settings_button(
        on_click=on_settings_click, size=50, icon_size=26
    )
    account_btn = build_account_button(
        on_click=on_account_click, size=50, icon_size=26
    )

    for button in (menu_btn, new_chat_btn, workspaces_btn, chats_btn, settings_btn, account_btn):
        button.gradient = BRAND_GRADIENT
        button.border = ft.Border.all(2, ft.Colors.WHITE)

    def handle_resize(e):
        span = max(RAIL_WIDTH_MAX - RAIL_WIDTH_MIN, 1)
        ratio = (e.width - RAIL_WIDTH_MIN) / span
        resize_menu_button(menu_btn, ratio)
        resize_new_chat_button(new_chat_btn, ratio)
        resize_workspaces_button(workspaces_btn, ratio)
        resize_chats_button(chats_btn, ratio)
        resize_settings_button(settings_btn, ratio)
        resize_account_button(account_btn, ratio)

    return ft.Container(
        width=RAIL_WIDTH_DEFAULT,
        bgcolor=color("#e6ffffff"),
        blur=14,
        border_radius=8,
        border=ft.Border.all(2, ft.Colors.WHITE),
        padding=ft.Padding.symmetric(horizontal=0, vertical=8),
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
                ft.Column(
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[settings_btn, account_btn],
                ),
            ],
        ),
    )


def _overlay_item(
    icon, label: str, on_click=None
) -> tuple[ft.Container, ft.Container, ft.Text]:
    label_text = ft.Text(
        label,
        font_family="Google Sans",
        color=color("#000000"),
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
        tooltip=label,
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=8, vertical=8),
        bgcolor=ft.Colors.TRANSPARENT,
        ink=True,
        animate=ft.Animation(duration=150, curve=ft.AnimationCurve.EASE_OUT),
        on_click=on_click,
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            controls=[
                ft.Container(
                    width=36,
                    height=36,
                    border_radius=18,
                    gradient=BRAND_GRADIENT,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, color=ft.Colors.WHITE, size=19),
                ),
                label_wrapper,
            ],
        ),
    )

    def handle_hover(e: ft.Event[ft.Container]):
        e.control.bgcolor = color("#1aff6666") if e.data else ft.Colors.TRANSPARENT
        e.control.update()

    row.on_hover = handle_hover
    # Возвращаем сам Text, чтобы не лезть в Optional-поле .content
    return row, label_wrapper, label_text


def build_menu_overlay(
    rail: ft.Container,
    page: ft.Page,
    on_new_chat_click=None,
    on_settings_click=None,
    on_workspaces_click=None,
    on_chats_click=None,
    on_account_click=None,
    get_chat_items=None,
    on_select_chat=None,
    get_active_chat_id=None,
):
    is_open = False

    menu_row, menu_wrapper, menu_text = _overlay_item(
        ft.Icons.MENU, "Меню"
    )
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
    account_row, account_wrapper, account_text = _overlay_item(
        ft.Icons.PERSON, "Аккаунт"
    )

    wrappers = (
        menu_wrapper,
        new_chat_wrapper,
        workspaces_wrapper,
        chats_wrapper,
        settings_wrapper,
        account_wrapper,
    )
    texts = (menu_text, new_chat_text, workspaces_text, chats_text, settings_text, account_text)

    chat_search = ft.TextField(label="Найти чат", prefix_icon=ft.Icons.SEARCH,
                              text_size=12, dense=True)
    recent_chats = ft.ListView(expand=True, spacing=6, build_controls_on_demand=True)
    chat_feedback = ft.Text('', size=12, color=color('#47747a'))
    chat_snapshot = []

    async def select_recent(chat_id):
        if is_open:
            await toggle()
        if on_select_chat:
            on_select_chat(chat_id)

    def render_recent(e=None):
        query = (chat_search.value or '').strip().casefold()
        active = get_active_chat_id() if get_active_chat_id else None
        def row(item):
            cid, title, subtitle, _ = item
            async def click(_):
                await select_recent(cid)
            return ft.Container(padding=ft.Padding.symmetric(horizontal=10, vertical=10),
                border_radius=14, bgcolor=color('#dff8f3') if cid == active else color('#f3fffc'),
                border=ft.Border.all(1, color('#a8ddd7')) if cid == active else None,
                ink=True, on_click=click, tooltip=title,
                content=ft.Row(spacing=9, controls=[
                    ft.Icon(ft.Icons.LOCK_OUTLINED if cid < 0 else ft.Icons.CHAT_BUBBLE_OUTLINE,
                            size=17, color=color('#087f8c')),
                    ft.Column(expand=True, spacing=3, controls=[
                        ft.Text(title, size=12, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                                color=color('#123b43'), weight=ft.FontWeight.W_600 if cid == active else None),
                        ft.Text(subtitle, size=10, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                color=color('#47747a'))])]))
        recent_chats.controls = [row(item) for item in chat_snapshot if not query or query in item[1].casefold()]
        if not chat_feedback.value.startswith('Не удалось'):
            chat_feedback.value = 'Чаты не найдены' if chat_snapshot else 'Здесь появятся ваши чаты'
        chat_feedback.visible = not recent_chats.controls
        from .palette import apply_palette
        apply_palette(recent_chats)
        if e:
            page.update()

    chat_search.on_change = render_recent
    history_panel = ft.Column(expand=True, spacing=10, visible=False,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[ft.Text('Ваши чаты', size=12, weight=ft.FontWeight.W_600, color=color('#087f8c')),
                  chat_search, chat_feedback, recent_chats])

    panel = ft.Container(
        width=RAIL_WIDTH_DEFAULT,
        top=0,
        bottom=0,
        left=0,
        bgcolor=color("#EAFBFA"),
        blur=14,
        border_radius=ft.BorderRadius.only(
            top_right=20, bottom_right=20
        ),
        border=ft.Border.all(2, color("#7DEED5")),
        padding=ft.Padding.symmetric(horizontal=10, vertical=12),
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        animate=ft.Animation(
            duration=PANEL_ANIMATION_MS, curve=ft.AnimationCurve.EASE_OUT_BACK
        ),
        shadow=ft.BoxShadow(
            blur_radius=24,
            spread_radius=2,
            color=color("#4400A896"),
        ),
        content=ft.Column(
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(
                    spacing=8,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[menu_row, new_chat_row, workspaces_row, chats_row],
                ),
                history_panel,
                ft.Column(
                    spacing=8,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[settings_row, account_row],
                ),
            ],
        ),
    )

    def refresh_recent():
        if not is_open:
            return
        try:
            chat_snapshot[:] = get_chat_items() if get_chat_items else []
            chat_feedback.value = ''
        except Exception as exc:
            chat_snapshot.clear()
            chat_feedback.value = f'Не удалось прочитать чаты: {exc}'
        render_recent()
        page.update()

    async def toggle():
        nonlocal is_open
        is_open = not is_open

        if is_open:
            refresh_recent()
            overlay_stack.visible = True
            rail.opacity = 0
            page.update()
            await asyncio.sleep(0.02)
            panel.width = min(PANEL_WIDTH, max(220, (page.width or PANEL_WIDTH + 32) - 32))
            for wrapper in wrappers:
                wrapper.width = min(LABEL_WIDTH, panel.width - 90)
            for text in texts:
                text.opacity = 1          # <- теперь тип точно ft.Text
            history_panel.visible = True
            page.update()
        else:
            history_panel.visible = False
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

    async def handle_scrim_click(_):
        await toggle()

    async def handle_panel_click(callback, event):
        await toggle()
        if callback is not None:
            callback(event)

    async def handle_new_chat_click(event):
        if on_new_chat_click is None:
            await handle_scrim_click(event)
        else:
            await handle_panel_click(on_new_chat_click, event)

    menu_row.on_click = handle_scrim_click
    new_chat_row.on_click = handle_new_chat_click

    async def handle_settings_click(event):
        if on_settings_click is None:
            await handle_scrim_click(event)
        else:
            await handle_panel_click(on_settings_click, event)

    async def handle_account_click(event):
        if on_account_click is None:
            await handle_scrim_click(event)
        else:
            await handle_panel_click(on_account_click, event)

    async def handle_workspaces_click(event):
        if on_workspaces_click is None:
            await handle_scrim_click(event)
        else:
            await handle_panel_click(on_workspaces_click, event)

    async def handle_chats_click(event):
        if on_chats_click is None:
            await handle_scrim_click(event)
        else:
            await handle_panel_click(on_chats_click, event)

    settings_row.on_click = handle_settings_click
    account_row.on_click = handle_account_click
    workspaces_row.on_click = handle_workspaces_click
    chats_row.on_click = handle_chats_click

    scrim = ft.Container(
        expand=True,
        bgcolor=color("#40000000"),
        blur=5,
        on_click=handle_scrim_click,
    )

    overlay_stack = ft.Stack(
        expand=True,
        visible=False,
        controls=[scrim, panel],
    )

    overlay_stack._xopilot_refresh_chats = refresh_recent
    return overlay_stack, toggle
