"""
Файл: /App/encryption/background.py
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

def build_background_layout(chat: ft.Control, prompt_container: ft.Control) -> ft.Container:
    bg = build_background()
    bg.padding = ft.padding.Padding.all(10)
    bg.content = ft.Column(
        expand=True,
        spacing=8,
        controls=[
            chat,
            ft.Row(
                controls=[
                    prompt_container,
                    # build_close_button(on_close),
                ],
            ),
        ],
    )
    return bg
