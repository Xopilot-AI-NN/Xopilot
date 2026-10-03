"""
Файл: /App/app/chats.py
Описание: Интерфейс списка чатов.
           Показывает поиск, позволяет переключаться между реальными чатами из БД,
           создавать новые и удалять существующие (chat_items приходит из
           chat_store.list_chat_items() — реальные (chat_id, title, subtitle, pinned)).
"""

import flet as ft
try:
    from .palette import color
except ImportError:
    from app.palette import color
try:
    from ..services import workspaces
except ImportError:
    from services import workspaces


def _chat_row(chat_id: int, title: str, subtitle: str, pinned: bool, on_select, on_delete, on_rename=None, active=False) -> ft.Container:
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=6, vertical=4),
        border_radius=12,
        bgcolor=color("#dff8f3") if active else None,
        content=ft.Row(
            spacing=6,
            controls=[
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=5),
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
                                bgcolor=color("#dff8f3"),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.LOCK_OUTLINED if chat_id < 0 else ft.Icons.CHAT_BUBBLE_OUTLINE, size=19, color=color("#087f8c")),
                            ),
                            ft.Column(
                                expand=True,
                                spacing=2,
                                controls=[
                                    ft.Text(title, size=13, color=color("#123b43"), no_wrap=True),
                                    ft.Text(subtitle, size=11, color=color("#47747a"), no_wrap=True),
                                ],
                            ),
                            ft.Icon(
                                ft.Icons.PUSH_PIN_OUTLINED if pinned else ft.Icons.CHEVRON_RIGHT,
                                size=17,
                                color=color("#087f8c"),
                            ),
                        ],
                    ),
                ),
                ft.IconButton(
                    icon=ft.Icons.EDIT_OUTLINED, tooltip="Переименовать чат",
                    icon_color=color("#087f8c"), icon_size=17, width=30, height=30,
                    padding=0, on_click=on_rename,
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color=color("#c94b4b"),
                    icon_size=17,
                    width=30,
                    height=30,
                    padding=0,
                    bgcolor=color("#ffe9e9"),
                    hover_color=color("#ffd2d2"),
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
    on_rename_chat=None,
    active_chat_id=None,
    on_move_chat=None,
) -> ft.AlertDialog:
    """on_select_chat(chat_id), on_create_chat(), on_delete_chat(chat_id) — синхронные коллбэки со
    стороны main.py, где живёт активный чат и лента сообщений (тот же стиль, что у
    open_settings/open_workspaces в main.py).
    """
    items = chat_items if chat_items is not None else []
    search = ft.TextField(
        hint_text="Поиск по чатам",
        prefix_icon=ft.Icons.SEARCH,
        bgcolor=color("#f3fffc"),
        border=ft.OutlineInputBorder(
            border_radius=12,
        ),
    )
    chat_rows = ft.Column(spacing=3)
    empty = ft.Text("", size=13, color=color("#47747a"), text_align=ft.TextAlign.CENTER)

    def move(chat_id):
        current = workspaces.chat_workspace(chat_id)
        choice = ft.Dropdown(label="Рабочее пространство", value=current["id"],
                             color=color("#123b43"), bgcolor=color("#f3fffc"),
                             options=[ft.DropdownOption(key=i["id"], text=i["name"])
                                      for i in workspaces.list_workspaces()])
        error = ft.Text("", color=color("#b3261e"))
        def save(_):
            try:
                if on_move_chat is None or on_move_chat(chat_id, choice.value) is not True:
                    return
                page.pop_dialog()
                if workspaces.selected_workspace() != workspaces.DEFAULT:
                    items[:] = workspaces.filter_chats(items)
                render()
                page.update()
            except Exception as exc:
                error.value = str(exc)
                page.update()
        page.show_dialog(ft.AlertDialog(
            bgcolor=color("#eafffa"), title=ft.Text("Переместить чат", color=color("#123b43")),
            content=ft.Column(tight=True, width=280, controls=[choice, error]),
            actions=[ft.TextButton(content="Отмена", on_click=lambda _: page.pop_dialog()),
                     ft.FilledButton(content="Переместить", on_click=save)]))

    def rename(chat_id, title):
        field = ft.TextField(value=title, label="Название чата", autofocus=True, color=color("#123b43"), bgcolor=color("#f3fffc"))
        def save(_):
            try:
                if on_rename_chat is None:
                    return
                new_title = on_rename_chat(chat_id, field.value or "")
                if not new_title:
                    return
            except Exception as exc:
                field.error_text = str(exc)
                field.update()
                return
            items[:] = [(cid, new_title if cid == chat_id else name, subtitle, pinned)
                        for cid, name, subtitle, pinned in items]
            page.pop_dialog()
            render()
            page.update()
        page.show_dialog(ft.AlertDialog(
            modal=True, bgcolor=color("#eafffa"), shape=ft.RoundedRectangleBorder(radius=18), title=ft.Text("Переименовать чат", color=color("#123b43")), content=field,
            actions=[ft.TextButton(content="Отмена", on_click=lambda _: page.pop_dialog()),
                     ft.FilledButton(content="Сохранить", on_click=save)],
        ))

    def confirm_delete(chat_id):
        def confirm(_):
            page.pop_dialog()
            delete_chat(chat_id)
        page.show_dialog(ft.AlertDialog(
            modal=True, bgcolor=color("#eafffa"), shape=ft.RoundedRectangleBorder(radius=18), title=ft.Text("Удалить чат?", color=color("#123b43")),
            content=ft.Text("Сообщения этого чата будут удалены. Это действие нельзя отменить.", color=color("#47747a")),
            actions=[ft.TextButton(content="Отмена", on_click=lambda _: page.pop_dialog()),
                     ft.FilledButton(content="Удалить", on_click=confirm)],
        ))

    def select_chat(chat_id: int):
        page.pop_dialog()
        if on_select_chat is not None:
            on_select_chat(chat_id)

    def delete_chat(chat_id: int):
        if on_delete_chat is None or on_delete_chat(chat_id) is not True:
            return
        items[:] = [item for item in items if item[0] != chat_id]
        render()
        page.update()

    def render(_=None):
        query = (search.value or "").lower().strip()
        chat_rows.controls = [
            ft.Column(spacing=0, controls=[_chat_row(
                chat_id,
                title,
                subtitle,
                pinned,
                lambda _, cid=chat_id: select_chat(cid),
                lambda _, cid=chat_id: confirm_delete(cid),
                lambda _, cid=chat_id, name=title: rename(cid, name),
                active=chat_id == active_chat_id,
            ), *([ft.TextButton(content="Переместить в пространство", icon=ft.Icons.DRIVE_FILE_MOVE_OUTLINED,
                               on_click=lambda _, cid=chat_id: move(cid))] if on_move_chat and chat_id > 0 else [])])
            for chat_id, title, subtitle, pinned in items
            if not query or query in title.lower()
        ]

        empty.value = "Ничего не найдено. Измените запрос." if items else "Пока нет чатов. Создайте первый диалог."
        empty.visible = not chat_rows.controls

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
        width=max(260, min(600, page.width - 64)) if isinstance(page.width, (int, float)) else 600,
        height=max(240, min(480, page.height - 140)) if isinstance(page.height, (int, float)) else 480,
        spacing=12,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        spacing=2,
                        expand=True,
                        controls=[
                            ft.Text("Чаты", size=24, weight=ft.FontWeight.BOLD, color=color("#123b43")),
                            ft.Text("Все диалоги Xopilot в одном месте", size=11, color=color("#47747a")),
                        ],
                    ),
                    ft.FilledButton(content="Новый чат", icon=ft.Icons.ADD_COMMENT, on_click=create_chat),
                ],
            ),
            search,
            ft.Text("ДИАЛОГИ", size=11, color=color("#087f8c"), weight=ft.FontWeight.BOLD),
            ft.Container(
                expand=True,
                bgcolor=color("#f3fffc"),
                border=ft.Border.all(1, color("#b9eee4")),
                border_radius=14,
                padding=ft.Padding.all(6),
                content=ft.ListView(expand=True, spacing=2, controls=[chat_rows, empty]),
            ),
        ],
    )
    return ft.AlertDialog(
        modal=False,
        content=content,
        bgcolor=color("#eafffa"),
        shape=ft.RoundedRectangleBorder(radius=18),
        inset_padding=ft.Padding.symmetric(horizontal=32, vertical=22),
        barrier_color=color("#88000000"),
        actions=[ft.TextButton(content="Закрыть", on_click=lambda _: page.pop_dialog())],
    )
