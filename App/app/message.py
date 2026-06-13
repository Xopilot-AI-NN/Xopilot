"""
Файл: /App/app/message.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __сообщения__
        клеится в чате
        имеют так и обычный вид сообщений так и
        canvas где можно печатсть совметсно с ИИ
        Фото где ИИ может его вставить ввиде ссылки на файл или 
            ссылки интернета и оно также будет отображатся
        Видео где ИИ может вставить ссылку на видео 
            из youtube и оно также будет воспроизводится

        делятся на 2 вида
        1. Сообщения от ИИ расположение слева
        2. Сообщения от пользователя расположение справа
"""

import flet as ft

def messages():
    def ai_message(text: str) -> ft.Container:
        def message_canvas():
            pass

        def message_photo():
            pass

        def message_video():
            pass
        
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

        return ft.Container(
            padding=ft.padding.Padding.symmetric(horizontal=12, vertical=9),
            border_radius=20,
            bgcolor=ft.Colors.WHITE_70,
            blur=1,
            content=ft.Text(
                "" if spans else text,
                font_family="Google Sans",
                spans=spans,
                color=ft.Colors.BLACK,
                size=14,
            ),
        )
    
    def user_message(text: str) -> ft.Container:
        return ft.Container(
            padding=ft.padding.Padding.symmetric(horizontal=12, vertical=9),
            border_radius=20,
            bgcolor="#ff6666ff",
            content=ft.Text(
                text,
                font_family="Google Sans",
                color=ft.Colors.WHITE,
                size=14,
            ),
        )


