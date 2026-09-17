"""
Файл: /App/app/chat.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Чат__
        клеится по середине выше строки для ввода в окне
"""



import flet as ft


def build_chat(controls: list, on_scroll=None) -> ft.Container:
    # reverse=True -- индекс 0 внизу, вид сразу стоит на последнем сообщении (как в Telegram):
    # исчезают и стартовый scroll_to(-1) с видимым прыжком, и загрузка всей истории --
    #ListView строит виджеты только для видимых элементов (build_controls_on_demand).
    return ft.Container(
        expand=True,
        bgcolor=ft.Colors.TRANSPARENT,
        content=ft.ListView(
            expand=True,
            reverse=True,
            spacing=12,
            padding=ft.Padding.only(left=4, top=4, right=4, bottom=12),
            controls=controls,
            on_scroll=on_scroll,
        ),
    )