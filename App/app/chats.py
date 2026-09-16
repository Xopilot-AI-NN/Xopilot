"""
Файл: /App/app/chats.py
Описание: Интерфейс списка чатов.
           Показывает поиск, позволяет переключаться между реальными чатами из БД,
           создавать новые и удалять существующие (chat_items приходит из
           chat_store.list_chat_items() — реальные (chat_id, title, subtitle, pinned)).
"""

import flet as ft


def _chat_row(chat_id: int, title: str, subtitle: str, pinned: bool, on_select, on_delete) -> ft.Container:
    return ft.Container(
        padding=ft.padding.Padding.symmetric(horizontal=6, vertical=4),
        border_radius=12,
        content=ft.Row(
            spacing=6,
            controls=[
                ft.Container(
                    expand=True,
                    padding=ft.padding.Padding.symmetric(horizontal=6, vertical=5),
                    border_radius=12,
                    ink=True,
                    on_click=on_select,
                    content=ft.Row(
                        spacing=11,
                        controls=[
                            ft.Container(
                                width=38,
                                height=38,
                                border_radius=19,
                                bgcolor="#dff8f3",
                                alignment=ft.alignment.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE, size=19, color="#087f8c"),
                            ),
                            ft.Column(
                                expand=True,
                                spacing=2,
                                controls=[
                                    ft.Text(title, size=13, color="#123b43", no_wrap=True),
                                    ft.Text(subtitle, size=11, color="#47747a", no_wrap=True),
                                ],
                            ),
                            ft.Icon(
                                ft.Icons.PUSH_PIN_OUTLINED if pinned else ft.Icons.CHEVRON_RIGHT,
                                size=17,
                                color="#087f8c",
                            ),
                        ],
                    ),
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color="#c94b4b",
                    icon_size=17,
                    width=30,
                    height=30,
                    padding=0,
                    bgcolor="#ffe9e9",
                    hover_color="#ffd2d2",
                    tooltip="Удалить чат",
                    on_click=on_delete,
                ),
            ],
        ),
    )


def build_chats_dialog(
    page: ft.Page,
    chat_items: list[tuple[int, str, str, bool]] | None = None,
    on_select_chat=None,
    on_create_chat=None,
    on_delete_chat=None,
) -> ft.AlertDialog:
    """on_select_chat(chat_id), on_create_chat(), on_delete_chat(chat_id) — синхронные коллбэки со
    стороны main.py, где живёт активный чат и лента сообщений (тот же стиль, что у
    open_settings/open_workspaces в main.py).
    """
    items = chat_items if chat_items is not None else []
    search = ft.TextField(
        hint_text="Поиск по чатам",
        prefix_icon=ft.Icons.SEARCH,
        border_radius=12,
        bgcolor="#f3fffc",
        border_color="#b9eee4",
        width=430,
    )
    chat_rows = ft.Column(spacing=3)

    def select_chat(chat_id: int):
        page.pop_dialog()
        if on_select_chat is not None:
            on_select_chat(chat_id)

    def delete_chat(chat_id: int):
        items[:] = [item for item in items if item[0] != chat_id]
        render()
        page.update()
        if on_delete_chat is not None:
            on_delete_chat(chat_id)

    def render(_=None):
        query = (search.value or "").lower().strip()
        chat_rows.controls = [
            _chat_row(
                chat_id,
                title,
                subtitle,
                pinned,
                lambda _, cid=chat_id: select_chat(cid),
                lambda _, cid=chat_id: delete_chat(cid),
            )
            for chat_id, title, subtitle, pinned in items
            if not query or query in title.lower()
        ]

    def search_chats(_):
        render()
        page.update()

    def create_chat(_):
        page.pop_dialog()
        if on_create_chat is not None:
            on_create_chat()

    search.on_change = search_chats
    render()
    content = ft.Column(
        width=600,
        height=480,
        spacing=12,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text("Чаты", size=24, weight=ft.FontWeight.BOLD, color="#123b43"),
                            ft.Text("Все диалоги Xopilot в одном месте", size=11, color="#47747a"),
                        ],
                    ),
                    ft.FilledButton("Новый чат", icon=ft.Icons.ADD_COMMENT, on_click=create_chat),
                ],
            ),
            search,
            ft.Text("ДИАЛОГИ", size=11, color="#087f8c", weight=ft.FontWeight.BOLD),
            ft.Container(
                expand=True,
                bgcolor="#f3fffc",
                border=ft.border.Border.all(1, "#b9eee4"),
                border_radius=14,
                padding=ft.padding.Padding.all(6),
                content=ft.ListView(expand=True, spacing=2, controls=[chat_rows]),
            ),
        ],
    )
    return ft.AlertDialog(
        modal=False,
        content=content,
        bgcolor="#eafffa",
        shape=ft.RoundedRectangleBorder(radius=18),
        inset_padding=ft.padding.Padding.symmetric(horizontal=32, vertical=22),
        barrier_color="#88000000",
        actions=[ft.TextButton("Закрыть", on_click=lambda _: page.pop_dialog())],
    )