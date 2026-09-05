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
            из youtube и оно также будет воспроизводиться

        делятся на 2 вида
        1. Сообщения от ИИ расположение слева
        2. Сообщения от пользователя расположение справа

        Пузыри обёрнуты в Container(alignment=LEFT/RIGHT), а не в Row:
        у Container в ListView ширина жёстко равна ширине чата, и alignment
        даёт вложенному пузырю ограниченные (не бесконечные, как в Row)
        ограничения ширины — текст переносится по словам вместо обрезания,
        а короткие сообщения по-прежнему облегают текст. Отступ с противоположной
        стороны не даёт пузырю растягиваться на всю ширину чата.

        История чата загружается из локальной БД (services.chat_store) — тестовые/демо-сообщения
        больше не хардкодятся здесь — см. services/chat_store.py::seed_demo_chat_if_empty.
"""



import flet as ft

from . import material as file_utils
from .buttons.message_actions import build_message_actions


def build_user_message(
    text: str,
    files: list[ft.FilePickerFile] | None = None,
    on_action=None,
    quote: str | None = None,
    reply_to: str | None = None,
    message_id: int | None = None,
) -> ft.Container:
    content = []
    if reply_to:
        content.append(
            ft.Container(
                bgcolor="#effffc",
                border=ft.border.Border.all(1, "#087f8c"),
                border_radius=12,
                padding=ft.padding.Padding.only(left=8, top=6, right=8, bottom=6),
                content=ft.Column(
                    spacing=2,
                    controls=[
                        ft.Text("ОТВЕТ НА СООБЩЕНИЕ", size=9, color="#087f8c", weight=ft.FontWeight.BOLD),
                        ft.Text(reply_to, size=12, color="#47747a", max_lines=2),
                    ],
                ),
            )
        )
    if quote:
        content.append(
            ft.Container(
                bgcolor="#effffc",
                border=ft.border.Border.all(1, "#20b486"),
                border_radius=12,
                padding=ft.padding.Padding.only(left=8, top=6, right=8, bottom=6),
                content=ft.Column(
                    spacing=2,
                    controls=[
                        ft.Text("ЦИТАТА", size=9, color="#20b486", weight=ft.FontWeight.BOLD),
                        ft.Text(quote, size=12, color="#47747a", italic=True, max_lines=3),
                    ],
                ),
            )
        )
    if files:
        content.append(
            ft.Row(
                spacing=6,
                tight=True,
                controls=[file_utils.build_file_tile(file) for file in files],
            )
        )
    content.append(ft.Text(text, font_family="Google Sans", color=ft.Colors.BLACK, size=14))

    actions = (
        build_message_actions(text, files, on_action, True, message_id)
        if on_action
        else ft.Container()
    )
    actions.opacity = 0
    actions.animate_opacity = 180

    bubble = ft.Container(
        padding=ft.padding.Padding.symmetric(horizontal=12, vertical=9),
        border_radius=20,
        bgcolor="#e6ffffff",
        blur=2,
        content=ft.Column(
            spacing=6,
            controls=[
                *content,
            ],
        ),
    )
    footer = ft.Row(
        alignment=ft.MainAxisAlignment.END,
        controls=[
            ft.Container(
                margin=ft.margin.Margin.only(top=2),
                content=actions,
            )
        ],
    )
    message = ft.Container(
        alignment=ft.alignment.Alignment.CENTER_RIGHT,
        padding=ft.padding.Padding.only(left=40),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.END,
            spacing=0,
            controls=[bubble, footer],
        ),
    )
    message.data = message_id if message_id is not None else text

    def handle_hover(e: ft.Event[ft.Container]):
        actions.opacity = 1 if e.data == "true" or e.data is True else 0
        actions.update()

    message.on_hover = handle_hover
    return message


def build_ai_message(text: str, on_action=None, message_id: int | None = None) -> ft.Container:
    """Пузырь сообщения ИИ (слева). Раньше это была внутренняя функция внутри messages(),
    вынесена на верхний уровень — чтобы рендерить отдельные сообщения из БД, а не только
    весь демо-список целиком."""
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

    bubble_content = ft.Column(
        spacing=4,
        controls=[
            ft.Text(
                "" if spans else text,
                font_family="Google Sans",
                spans=spans,
                color=ft.Colors.BLACK,
                size=14,
            ),
        ],
    )
    bubble = ft.Container(
        padding=ft.padding.Padding.symmetric(horizontal=12, vertical=9),
        border_radius=20,
        bgcolor="#e6ffffff",
        blur=2,
        content=bubble_content,
    )

    actions = (
        build_message_actions(text, None, on_action, False, message_id)
        if on_action
        else ft.Container()
    )
    actions.opacity = 0
    actions.animate_opacity = 180
    footer = ft.Row(
        alignment=ft.MainAxisAlignment.START,
        controls=[
            ft.Container(
                margin=ft.margin.Margin.only(top=2),
                content=actions,
            )
        ],
    )
    message = ft.Container(
        alignment=ft.alignment.Alignment.CENTER_LEFT,
        padding=ft.padding.Padding.only(right=40),
        content=ft.Column(spacing=0, controls=[bubble, footer]),
    )
    message.data = message_id if message_id is not None else text

    def handle_hover(e: ft.Event[ft.Container]):
        actions.opacity = 1 if e.data == "true" or e.data is True else 0
        actions.update()

    message.on_hover = handle_hover
    return message