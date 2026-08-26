"""
Файл: /App/app/progress.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Прогресбар__
           Нужен для определения на сколько завершена задача
           к примеру на сколько агент ИИ завершил работу над проектом
           или ещё чего то
"""


import flet as ft


def build_progress(value: float | None = 0) -> ft.Container:
    return ft.Container(
        height=24,
        border_radius=8,
        border=ft.border.Border.all(2, "#d9ffe6"),
        bgcolor="#00c753",
        padding=ft.padding.Padding.symmetric(horizontal=8, vertical=5),
        content=ft.ProgressBar(
            value=value,
            color="#ff6666ff",
            bgcolor="#d9ffe6",
        ),
    )
