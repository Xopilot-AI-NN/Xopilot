"""
Файл: /App/app/chats.py
Описание: Интерфейс списка чатов.
           Показывает поиск, закреплённые и недавние диалоги.
"""

import flet as ft


CHAT_ITEMS = [
    ("Продолжение оформления", "Сегодня · 12 сообщений", True),
    ("Идеи для локального ИИ", "Вчера · 8 сообщений", False),
    ("Материалы проекта Xopilot", "18 февраля · 24 сообщения", False),
    ("Настройка интерфейса", "12 февраля · 16 сообщений", False),
]


def _chat_row(title: str, subtitle: str, pinned: bool, on_click) -> ft.Container:
    return ft.Container(
        padding=ft.padding.Padding.symmetric(horizontal=12, vertical=9),
        border_radius=12,
        ink=True,
        on_click=on_click,
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
                ft.Icon(ft.Icons.PUSH_PIN_OUTLINED if pinned else ft.Icons.CHEVRON_RIGHT, size=17, color="#087f8c"),
            ],
        ),
    )


def build_chats_dialog(
    page: ft.Page,
    chat_list: ft.ListView | None = None,
    chat_items: list[tuple[str, str, bool]] | None = None,
) -> ft.AlertDialog:
    items = chat_items if chat_items is not None else CHAT_ITEMS
    search = ft.TextField(
        hint_text="Поиск по чатам",
        prefix_icon=ft.Icons.SEARCH,
        border_radius=12,
        bgcolor="#f3fffc",
        border_color="#b9eee4",
        width=430,
    )
    chat_rows = ft.Column(spacing=3)

    def open_chat(title: str):
        if chat_list is not None:
            page.pop_dialog()
            chat_list.update()

    def render(_=None):
        query = (search.value or "").lower().strip()
        chat_rows.controls = [
            _chat_row(title, subtitle, pinned, lambda _, name=title: open_chat(name))
            for title, subtitle, pinned in items
            if not query or query in title.lower()
        ]

    def search_chats(_):
        render()
        page.update()

    def create_chat(_):
        items.insert(0, ("Новый чат", "Только что создан", True))
        search.value = ""
        render()
        page.update()

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
