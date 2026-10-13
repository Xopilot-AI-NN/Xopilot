"""
Файл: /App/app/background.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __задний фон__
        клеится сзади всех элементов в окне
"""



import flet as ft
try:
    from .palette import color, outline_color
except ImportError:
    from app.palette import color, outline_color
import platform

def build_background() -> ft.Container:
    return ft.Container(
        expand=True,
        bgcolor=color("#b3f2ff"),
    )

def build_background_layout(
    chat: ft.Control,
    prompt_container: ft.Control,
    menu: ft.Control,
    menu_overlay: ft.Control | None = None,
    header: ft.Control | None = None,
    empty_state: ft.Control | None = None,
    visual_background: ft.Control | None = None,
    compact: bool = False,
) -> ft.Container:
    bg = build_background()
    bg.padding = ft.Padding.all(4 if compact else 10)
    linux_layout = platform.system() == "Linux"
    input_side_margin = 12 if linux_layout else 4
    input_bottom_margin = 8 if linux_layout else 0

    input_area = ft.Container(
        padding=ft.Padding.only(
            left=input_side_margin,
            right=input_side_margin,
        ),
        content=prompt_container,
    )

    main_column = ft.Column(
        expand=True,
        spacing=0,
        controls=[
            *([header] if header is not None else []),
            ft.Stack(expand=True, controls=[*([visual_background] if visual_background is not None else []),
                chat, *([empty_state] if empty_state is not None else [])]),
            ft.Container(
                margin=ft.Margin.only(bottom=input_bottom_margin),
                content=input_area,
            ),
        ],
    )

    main_content = ft.Container(
        expand=True,
        bgcolor=color("#d9ffe6"),
        border_radius=16,
        border=ft.Border.all(2, outline_color()),
        content=main_column,
    )

    menu.visible = not compact
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

    def set_compact(value):
        menu.visible = not value
        bg.padding = ft.Padding.all(0 if value else 10)
        main_content.border_radius = 0 if value else 16
        main_content.border = None if value else ft.Border.all(2, outline_color())
        input_area.padding = ft.Padding.symmetric(horizontal=8 if value else input_side_margin)
        main_column.controls[-1].margin = ft.Margin.only(bottom=8 if value else input_bottom_margin)
    set_compact(compact)
    bg._xopilot_set_compact = set_compact
    return bg
