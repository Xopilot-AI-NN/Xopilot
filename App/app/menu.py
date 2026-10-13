"""Navigation rail and a fixed-width sliding drawer.

Only the drawer/rail update while opening. Translation is animated by Flutter,
without resizing every label or relaying animation frames through Python.
"""

import asyncio
import flet as ft
try:
    from .palette import color, outline_color
except ImportError:
    from app.palette import color, outline_color
import platform

from .buttons.account import build_account_button, resize_account_button
from .buttons.menu import build_menu_button, resize_menu_button
from .buttons.new_chat import build_new_chat_button, resize_new_chat_button
from .buttons.settings import build_settings_button, resize_settings_button
from .buttons.workspaces import build_workspaces_button, resize_workspaces_button
from .buttons.chats import build_chats_button, resize_chats_button
from .buttons.brand import style_brand_button
from .button_colors import action_role
try:
    from ..services.platforms import is_android
except ImportError:
    from services.platforms import is_android

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
    on_private_click=None,
    on_materials_click=None,
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

    from .buttons.brand import brand_button
    private_btn = brand_button(ft.Icons.LOCK_OUTLINED, "Защищённые чаты", on_private_click, size=50)
    materials_btn=brand_button(ft.Icons.LIBRARY_BOOKS_OUTLINED,'Материалы',on_materials_click,size=50)

    for button in (menu_btn, new_chat_btn, workspaces_btn, chats_btn, settings_btn, account_btn):
        style_brand_button(button, action_role(button.content.icon, button.tooltip))
        button.on_hover = None

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
        blur=None,
        border_radius=8,
        border=ft.Border.all(2, outline_color()),
        padding=ft.Padding.symmetric(horizontal=0, vertical=8),
        opacity=1,
        animate_opacity=200,
        size_change_interval=80,
        on_size_change=None if is_android() else handle_resize,
        content=ft.Column(
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[menu_btn,new_chat_btn,workspaces_btn,chats_btn,materials_btn,private_btn],
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
        opacity=1,
    )

    label_wrapper = ft.Container(
        width=LABEL_WIDTH,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
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
                style_brand_button(ft.Container(
                    width=36,
                    height=36,
                    border_radius=18,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, size=19),
                ), action_role(icon, label)),
                label_wrapper,
            ],
        ),
    )

    def handle_hover(e: ft.Event[ft.Container]):
        e.control.bgcolor = color("#ddf8f2") if e.data else ft.Colors.TRANSPARENT
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
    on_private_click=None,
    get_chat_items=None,
    on_select_chat=None,
    get_active_chat_id=None,
    on_delete_chat=None,
    on_materials_click=None,
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

    private_row, private_wrapper, private_text = _overlay_item(ft.Icons.LOCK_OUTLINED, "Защищённые чаты")
    materials_row,materials_wrapper,materials_text=_overlay_item(ft.Icons.LIBRARY_BOOKS_OUTLINED,'Материалы')

    wrappers = (
        materials_wrapper,
        private_wrapper,
        menu_wrapper,
        new_chat_wrapper,
        workspaces_wrapper,
        chats_wrapper,
        settings_wrapper,
        account_wrapper,
    )
    texts = (materials_text,private_text,menu_text,new_chat_text,workspaces_text,chats_text,settings_text,account_text)

    chat_search = ft.TextField(label="Найти чат", prefix_icon=ft.Icons.SEARCH,
                              text_size=12, dense=True)
    recent_chats = ft.ListView(expand=True, spacing=6, build_controls_on_demand=True)
    chat_feedback = ft.Text('', size=12, color=color('#47747a'))
    chat_snapshot = []
    rendered_snapshot = None
    transition_lock = asyncio.Lock()

    async def select_recent(chat_id):
        if is_open:
            await toggle()
        if on_select_chat:
            on_select_chat(chat_id)

    def render_recent(e=None):
        nonlocal rendered_snapshot
        query = (chat_search.value or '').strip().casefold()
        active = get_active_chat_id() if get_active_chat_id else None
        signature = (tuple(chat_snapshot), query, active, chat_feedback.value if chat_feedback.value.startswith('Не удалось') else '')
        if rendered_snapshot == signature:
            return
        rendered_snapshot = signature
        def row(item):
            cid, title, subtitle, _ = item
            async def click(_):
                await select_recent(cid)
            def remove(_):
                def confirmed(_):
                    page.pop_dialog()
                    if on_delete_chat and on_delete_chat(cid):refresh_recent()
                page.show_dialog(ft.AlertDialog(modal=True,bgcolor=color('#eafffa'),title=ft.Text('Удалить чат?'),
                    content=ft.Text('«'+title+'» и его сообщения будут удалены. Остальные чаты сохранятся.'),
                    actions=[ft.TextButton(content='Отмена',on_click=lambda _:page.pop_dialog()),
                             ft.FilledButton(content='Удалить',on_click=confirmed)]))
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
                                color=color('#47747a'))]),
                    *([ft.IconButton(icon=ft.Icons.DELETE_OUTLINE,tooltip='Удалить чат: '+title,
                        icon_color=color('#c94b4b'),on_click=remove)] if on_delete_chat else [])]))
        recent_chats.controls = [row(item) for item in chat_snapshot if not query or query in item[1].casefold()]
        if not chat_feedback.value.startswith('Не удалось'):
            chat_feedback.value = 'Чаты не найдены' if chat_snapshot else 'Здесь появятся ваши чаты'
        chat_feedback.visible = not recent_chats.controls
        from .palette import apply_palette
        apply_palette(recent_chats)
        if e:
            page.update(history_panel)

    chat_search.on_change = render_recent
    history_panel = ft.Column(expand=True, spacing=10, visible=True,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[ft.Text('Ваши чаты', size=12, weight=ft.FontWeight.W_600, color=color('#087f8c')),
                  chat_search, chat_feedback, recent_chats])

    panel = ft.Container(
        width=PANEL_WIDTH,
        top=0,
        bottom=0,
        left=0,
        bgcolor=color("#EAFBFA"),
        blur=None,
        border_radius=ft.BorderRadius.only(
            top_right=20, bottom_right=20
        ),
        border=ft.Border.all(2, color("#7DEED5")),
        padding=ft.Padding.symmetric(horizontal=10, vertical=12),
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        offset=ft.Offset(-1, 0),
        animate_offset=ft.Animation(duration=PANEL_ANIMATION_MS, curve=ft.AnimationCurve.EASE_OUT_CUBIC),
        shadow=ft.BoxShadow(
            blur_radius=8,
            spread_radius=0,
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
                    controls=[menu_row,new_chat_row,workspaces_row,chats_row,materials_row,private_row],
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

    def set_recent(items, error=''):
        chat_snapshot[:] = items
        chat_feedback.value = error
        render_recent()

    def refresh_recent():
        if not is_open:
            return
        try:
            set_recent(get_chat_items() if get_chat_items else [])
        except Exception as exc:
            set_recent([], f'Не удалось прочитать чаты: {exc}')
        page.update(history_panel)

    async def toggle():
        nonlocal is_open
        async with transition_lock:
            is_open = not is_open
            if is_open:
                # Read encrypted summaries off the UI loop before animating.
                try:
                    items = await asyncio.to_thread(get_chat_items) if get_chat_items else []
                    set_recent(items)
                except Exception as exc:
                    set_recent([], f'Не удалось прочитать чаты: {exc}')
                panel.width = min(PANEL_WIDTH, max(220, (page.width or PANEL_WIDTH + 32) - 32))
                for wrapper in wrappers:
                    wrapper.width = min(LABEL_WIDTH, panel.width - 90)
                overlay_stack.visible = True
                rail.opacity = 0
                panel.offset = ft.Offset(-1, 0)
                page.update(overlay_stack, rail)
                await asyncio.sleep(0.016)
                panel.offset = ft.Offset(0, 0)
                page.update(panel)
            else:
                panel.offset = ft.Offset(-1, 0)
                page.update(panel)
                await asyncio.sleep(PANEL_ANIMATION_MS / 1000)
                overlay_stack.visible = False
                rail.opacity = 1
                page.update(overlay_stack, rail)

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

    async def handle_private_click(event):
        await handle_panel_click(on_private_click, event)
    private_row.on_click = handle_private_click
    async def handle_materials_click(event):
        await handle_panel_click(on_materials_click,event)
    materials_row.on_click=handle_materials_click

    settings_row.on_click = handle_settings_click
    account_row.on_click = handle_account_click
    workspaces_row.on_click = handle_workspaces_click
    chats_row.on_click = handle_chats_click

    scrim = ft.Container(
        expand=True,
        bgcolor=color("#40000000"),
        blur=None,
        on_click=handle_scrim_click,
    )

    overlay_stack = ft.Stack(
        expand=True,
        visible=False,
        controls=[scrim, panel],
    )

    overlay_stack._xopilot_refresh_chats = refresh_recent
    return overlay_stack, toggle
