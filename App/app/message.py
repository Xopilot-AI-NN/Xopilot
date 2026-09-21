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

        История чата загружается из локальной БД (services.chat_store).
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
                border=ft.Border.all(1, "#087f8c"),
                border_radius=12,
                padding=ft.Padding.only(left=8, top=6, right=8, bottom=6),
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
                border=ft.Border.all(1, "#20b486"),
                border_radius=12,
                padding=ft.Padding.only(left=8, top=6, right=8, bottom=6),
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
        padding=ft.Padding.symmetric(horizontal=12, vertical=9),
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
                margin=ft.Margin.only(top=2),
                content=actions,
            )
        ],
    )
    message = ft.Container(
        alignment=ft.Alignment.CENTER_RIGHT,
        padding=ft.Padding.only(left=40),
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


_AI_AUTHOR = "Zephyr"
_TEXT_COLOR = ft.Colors.BLACK


def _md_style(size: int = 14, **kwargs) -> ft.TextStyle:
    params = {"font_family": "Google Sans", "color": _TEXT_COLOR, **kwargs}
    return ft.TextStyle(size=size, **params)


def _ai_markdown_style() -> ft.MarkdownStyleSheet:
    """Единый шрифт/цвет для всех элементов Markdown в пузыре ИИ."""
    bold = ft.FontWeight.BOLD
    return ft.MarkdownStyleSheet(
        p_text_style=_md_style(),
        strong_text_style=_md_style(weight=bold),
        em_text_style=_md_style(italic=True),
        del_text_style=_md_style(decoration=ft.TextDecoration.LINE_THROUGH),
        a_text_style=_md_style(color="#087f8c", decoration=ft.TextDecoration.UNDERLINE),
        h1_text_style=_md_style(22, weight=bold),
        h2_text_style=_md_style(19, weight=bold),
        h3_text_style=_md_style(16, weight=bold),
        h4_text_style=_md_style(15, weight=bold),
        h5_text_style=_md_style(14, weight=bold),
        h6_text_style=_md_style(14, weight=bold),
        blockquote_text_style=_md_style(color="#47747a"),
        list_bullet_text_style=_md_style(),
        table_head_text_style=_md_style(weight=bold),
        table_body_text_style=_md_style(),
        code_text_style=_md_style(13, bgcolor="#dff8f3", font_family="monospace"),
    )


def _ai_markdown_value(text: str) -> str:
    """Имя автора в начале ответа («Zephyr: ...») как раньше выделяем жирным."""
    if text.startswith(_AI_AUTHOR):
        return f"**{_AI_AUTHOR}**{text[len(_AI_AUTHOR):]}"
    return text


def build_ai_message(text: str, on_action=None, message_id: int | None = None) -> ft.Container:
    """Пузырь сообщения ИИ (слева). Ответ рендерится как Markdown (GitHub Flavored):
    **жирный**, *курсив*, заголовки, списки, таблицы, код с подсветкой, ссылки.
    Кнопка «Копировать» и цитаты работают с исходным Markdown-текстом."""
    bubble_content = ft.Column(
        spacing=4,
        controls=[
            ft.Markdown(
                value=_ai_markdown_value(text),
                selectable=True,
                extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                code_theme=ft.MarkdownCodeTheme.GITHUB,
                md_style_sheet=_ai_markdown_style(),
                soft_line_break=True,
                auto_follow_links=True,
            ),
        ],
    )
    bubble = ft.Container(
        padding=ft.Padding.symmetric(horizontal=12, vertical=9),
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
                margin=ft.Margin.only(top=2),
                content=actions,
            )
        ],
    )
    message = ft.Container(
        alignment=ft.Alignment.CENTER_LEFT,
        padding=ft.Padding.only(right=40),
        content=ft.Column(spacing=0, controls=[bubble, footer]),
    )
    message.data = message_id if message_id is not None else text

    def handle_hover(e: ft.Event[ft.Container]):
        actions.opacity = 1 if e.data == "true" or e.data is True else 0
        actions.update()

    message.on_hover = handle_hover
    return message
