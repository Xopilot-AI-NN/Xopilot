"""
Файл: /App/app/background.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __задний фон__
        клеится сзади всех элементов в окне
"""



import flet as ft

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

    main_row = ft.Row(
        expand=True,
        spacing=8,
        controls=[
            menu,
            ft.Column(
                expand=True,
                spacing=8,
                controls=[
                    chat,
                    ft.Row(
                        controls=[
                            prompt_container,
                        ],
                    ),
                ],
            ),
        ],
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