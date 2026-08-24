"""
Файл: /App/app/message.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __сообщения__
        клеится в чате
        имеют так и обычный вид сообщений так и
        canvas где можно печатсть совметстно с ИИ
        Фото где ИИ может его вставить ввиде ссылки на файл или 
            ссылки интернета и оно также будет отображатся
        Видео где ИИ может вставить ссылку на видео 
            из youtube и оно также будет воспроизводится

        делятся на 2 вида
        1. Сообщения от ИИ расположение слева
        2. Сообщения от пользователя расположение справа

        Пузыри обёрнуты в Container(alignment=LEFT/RIGHT), а не в Row:
        у Container в ListView ширина жёстко равна ширине чата, и alignment
        даёт вложенному пузырю ограниченные (не бесконечные, как в Row)
        ограничения ширины — текст переносится по словам вместо обрезания,
        а короткие сообщения по-прежнему облегают текст. Отступ с противоположной
        стороны не даёт пузырю растягиваться на всю ширину чата.
"""



import flet as ft

from . import files as file_utils


def build_user_message(text: str, files: list[ft.FilePickerFile] | None = None) -> ft.Container:
    content = []
    if files:
        content.append(
            ft.Column(
                spacing=4,
                controls=[
                    ft.Row(
                        spacing=5,
                        controls=[
                            ft.Icon(ft.Icons.ATTACH_FILE, size=16, color="#087f8c"),
                            ft.Text(
                                f"{file.name} ({file_utils.format_file_size(file.size)})",
                                size=12,
                                color="#123b43",
                            ),
                        ],
                    )
                    for file in files
                ],
            )
        )
    content.append(
        ft.Text(text, font_family="Google Sans", color=ft.Colors.BLACK, size=14)
    )

    bubble = ft.Container(
        padding=ft.padding.Padding.symmetric(horizontal=12, vertical=9),
        border_radius=20,
        bgcolor="#e6ffffff",
        blur=2,
        content=ft.Column(spacing=6, controls=content),
    )
    return ft.Container(
        alignment=ft.alignment.Alignment.CENTER_RIGHT,
        padding=ft.padding.Padding.only(left=40),
        content=bubble,
    )

def messages() -> list[ft.Control]:
    def ai_message(text: str) -> ft.Container:
        author = "Zephyr"
        spans = None

        if text.startswith(author):
            spans = [
                ft.TextSpan(
                    author,
                    style=ft.TextStyle(weight=ft.FontWeight.BOLD),
                ),
                ft.TextSpan(text[len(author):]),
            ]

        bubble = ft.Container(
            padding=ft.padding.Padding.symmetric(horizontal=12, vertical=9),
            border_radius=20,
            bgcolor="#e6ffffff",
            blur=2,
            content=ft.Text(
                "" if spans else text,
                font_family="Google Sans",
                spans=spans,
                color=ft.Colors.BLACK,
                size=14,
            ),
        )

        return ft.Container(
            alignment=ft.alignment.Alignment.CENTER_LEFT,
            padding=ft.padding.Padding.only(right=40),
            content=bubble,
        )

    return [
        ai_message("Zephyr: Чем займёмся сегодня?"),
        build_user_message("Продолжим оформление приложения."),
        ai_message("Zephyr: Готов. Поддержу стиль, компоненты и логику в одном аккуратном интерфейсе."),
    ]