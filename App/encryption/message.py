"""
Файл: /App/encryption/message.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __сообщения__
        клеится в чате
"""



import flet as ft

def build_message(text: str) -> ft.Container:
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

def build_initial_messages() -> list[ft.Container]:
    return [
        build_message("Zephyr: 🔑 Для доступа к истории требуется ваш пароль от учётной записи Microsoft."),
        build_message("Zephyr: Важно: в целях безопасности и защиты вашей конфиденциальности, ваш пароль используется только локально на этом устройстве для аутентификации и никуда не передаётся. Ваши данные остаются под вашим полным контролем."),
    ]
