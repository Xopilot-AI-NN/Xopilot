"""
Файл: /App/app/workspace_browser.py
Описание: Интерфейс рабочих пространств.
           Показывает проекты и позволяет создать новое пространство.
"""

import flet as ft


WORKSPACES = [
    ("Xopilot", "Основной проект", ft.Icons.AUTO_AWESOME),
    ("Локальный ИИ", "Модели и эксперименты", ft.Icons.SMART_TOY_OUTLINED),
    ("Дизайн приложения", "Макеты и материалы", ft.Icons.PALETTE_OUTLINED),
]


def _workspace_card(name: str, description: str, icon, on_click) -> ft.Container:
    return ft.Container(
        width=178,
        height=132,
        padding=ft.padding.Padding.all(12),
        bgcolor="#f3fffc",
        border=ft.border.Border.all(1, "#b9eee4"),
        border_radius=14,
        ink=True,
        on_click=on_click,
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Container(
                    width=38,
                    height=38,
                    border_radius=12,
                    bgcolor="#dff8f3",
                    alignment=ft.alignment.Alignment.CENTER,
                    content=ft.Icon(icon, size=20, color="#087f8c"),
                ),
                ft.Text(name, size=13, color="#123b43", no_wrap=True),
                ft.Text(description, size=11, color="#47747a", max_lines=2),
            ],
        ),
    )


def build_workspaces_dialog(
    page: ft.Page,
    workspace_items: list[tuple[str, str, ft.IconData]] | None = None,
) -> ft.AlertDialog:
    items = workspace_items if workspace_items is not None else WORKSPACES
    cards = ft.Row(spacing=10, wrap=True, run_spacing=10)
    selected = ft.Text("Выберите пространство для работы", size=11, color="#47747a")

    def open_workspace(name: str):
        selected.value = f"Открыто пространство «{name}»"
        selected.update()

    def save_workspace(dialog: ft.AlertDialog, name_field: ft.TextField):
        name = (name_field.value or "").strip()
        if not name:
            name_field.error_text = "Введите название пространства"
            name_field.update()
            return
        items.append((name, "Новое рабочее пространство", ft.Icons.FOLDER_OUTLINED))
        render()
        selected.value = f"Создано пространство «{name}»"
        page.pop_dialog()
        page.update()

    def create_workspace(_):
        name_field = ft.TextField(label="Название проекта", autofocus=True)
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Новое пространство", color="#123b43"),
            content=name_field,
            actions=[
                ft.TextButton("Отмена", on_click=lambda _: page.pop_dialog()),
                ft.FilledButton("Создать", on_click=lambda _: save_workspace(dialog, name_field)),
            ],
        )
        page.show_dialog(dialog)

    def render():
        cards.controls = [
            _workspace_card(name, description, icon, lambda _, item=name: open_workspace(item))
            for name, description, icon in items
        ]

    render()
    content = ft.Column(
        width=600,
        height=430,
        spacing=14,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text("Рабочие пространства", size=24, weight=ft.FontWeight.BOLD, color="#123b43"),
                            ft.Text("Отдельные проекты, материалы и контекст", size=11, color="#47747a"),
                        ],
                    ),
                    ft.IconButton(
                        icon=ft.Icons.ADD,
                        tooltip="Создать пространство",
                        bgcolor="#b9eee4",
                        icon_color="#087f8c",
                        on_click=create_workspace,
                    ),
                ],
            ),
            selected,
            ft.Container(
                expand=True,
                bgcolor="#eafffa",
                content=ft.ListView(expand=True, controls=[cards]),
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
