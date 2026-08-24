"""
Файл: /App/app/background.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __задний фон__
        клеится сзади всех элементов в окне
"""



import flet as ft
import platform

def build_background() -> ft.Container:
    return ft.Container(
        expand=True,
        bgcolor="#b3f2ff",
    )

def build_background_layout(
    chat: ft.Control,
    prompt_container: ft.Control,
    menu: ft.Control,
    menu_overlay: ft.Control | None = None
) -> ft.Container:
    bg = build_background()
    bg.padding = ft.padding.Padding.all(10)
    linux_layout = platform.system() == "Linux"
    input_side_margin = 100 if linux_layout else 0
    input_bottom_margin = 8 if linux_layout else 0

    input_area = ft.Container(
        padding=ft.padding.Padding.only(
            left=input_side_margin,
            right=input_side_margin,
        ),
        content=prompt_container,
    )

    main_column = ft.Column(
        expand=True,
        spacing=0,
        controls=[
            chat,
            ft.Container(
                margin=ft.margin.Margin.only(bottom=input_bottom_margin),
                content=input_area,
            ),
        ],
    )

    main_content = ft.Container(
        expand=True,
        bgcolor="#00c753",
        border_radius=8,
        border=ft.border.Border.all(2, "#d9ffe6"),
        content=main_column,
    )

    main_row = ft.Row(
        expand=True,
        spacing=8,
        controls=[menu, main_content],
    )

    if menu_overlay is not None:
        # Stack кладёт выезжающее меню поверх main_row целиком —
        # оттого оно накрывает и чат, и строку ввода, а не только часть окна.
        bg.content = ft.Stack(
            expand=True,
            controls=[main_row, menu_overlay],
        )
    else:
        bg.content = main_row

    return bg