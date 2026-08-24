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

from . import material as file_utils
from .buttons.message_actions import build_message_actions


def build_user_message(
    text: str,
    files: list[ft.FilePickerFile] | None = None,
    on_action=None,
    quote: str | None = None,
    reply_to: str | None = None,
) -> ft.Container:
    content = []
    if reply_to:
        content.append(
            ft.Container(
                bgcolor="#dff8f3",
                border=ft.border.Border.only(left=ft.BorderSide(3, "#087f8c")),
                padding=ft.padding.Padding.only(left=8, top=5, right=8, bottom=5),
                content=ft.Column(
                    spacing=2,
                    controls=[
                        ft.Text("Ответ на сообщение", size=10, color="#087f8c", weight=ft.FontWeight.BOLD),
                        ft.Text(reply_to, size=12, color="#47747a", max_lines=2),
                    ],
                ),
            )
        )
    if quote:
        content.append(
            ft.Container(
                bgcolor="#f1fffb",
                border=ft.border.Border.only(left=ft.BorderSide(3, "#20b486")),
                padding=ft.padding.Padding.only(left=8, top=5, right=8, bottom=5),
                content=ft.Text(quote, size=12, color="#47747a", italic=True, max_lines=3),
            )
        )
    if files:
        content.append(
            ft.Column(
                spacing=4,
                controls=[
                    ft.Container(
                        bgcolor="#dff8f3",
                        border_radius=8,
                        padding=ft.padding.Padding.all(4),
                        content=ft.Row(
                            spacing=6,
                            tight=True,
                            controls=[
                                (
                                    ft.Image(
                                        src=file.path or "",
                                        width=44,
                                        height=44,
                                        fit=ft.BoxFit.COVER,
                                        border_radius=6,
                                    )
                                    if file_utils.is_image_file(file)
                                    else ft.Icon(
                                        file_utils.file_icon(file),
                                        size=30,
                                        color="#087f8c",
                                    )
                                ),
                                ft.Column(
                                    spacing=0,
                                    tight=True,
                                    controls=[
                                        ft.Text(file.name, size=12, color="#123b43", no_wrap=True),
                                        ft.Text(
                                            file_utils.format_file_size(file.size),
                                            size=10,
                                            color="#47747a",
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    )
                    for file in files
                ],
            )
        )
    content.append(ft.Text(text, font_family="Google Sans", color=ft.Colors.BLACK, size=14))

    actions = (
        build_message_actions(text, files, on_action, True)
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
    message.data = text

    def handle_hover(e: ft.Event[ft.Container]):
        actions.opacity = 1 if e.data == "true" or e.data is True else 0
        actions.update()

    message.on_hover = handle_hover
    return message

def messages(on_action=None) -> list[ft.Control]:
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
            build_message_actions(text, None, on_action, False)
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

        def handle_hover(e: ft.Event[ft.Container]):
            actions.opacity = 1 if e.data == "true" or e.data is True else 0
            actions.update()

        message.on_hover = handle_hover
        return message

    return [
        ai_message("Zephyr: Чем займёмся сегодня?"),
        build_user_message("Продолжим оформление приложения.", on_action=on_action),
        build_user_message(
            "Прикрепляю материалы для проверки.",
            [ft.FilePickerFile(id=1001, name="brief.pdf", size=248832, path="demo/brief.pdf")],
            on_action=on_action,
        ),
        build_user_message(
            "Да, именно этот вариант стоит оставить.",
            on_action=on_action,
            quote="Кнопки действий должны быть доступны прямо у сообщения.",
        ),
        build_user_message(
            "Добавлю это в следующую версию.",
            [ft.FilePickerFile(id=1002, name="screen.png", size=1572864, path="./Icons/Xopilot-icon-apk.png")],
            on_action=on_action,
            reply_to="Пришли, пожалуйста, текущий экран приложения.",
        ),
        ai_message("Zephyr: Готов. Поддержу стиль, компоненты и логику в одном аккуратном интерфейсе."),
    ]