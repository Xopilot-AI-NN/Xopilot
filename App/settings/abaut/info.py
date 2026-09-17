"""
Файл: /App/settings/abaut/info.py
Описание: __Блок информации__.
           Отображает версию, назначение приложения и разработчика.
"""

import flet as ft


ABOUT_WIDTH = 520
TEXT_WIDTH = 455


def build_about_row() -> ft.Container:
    """Верхний hero-блок страницы «О программе» с иконкой приложения."""
    return ft.Container(
        width=ABOUT_WIDTH,
        padding=ft.Padding.only(top=8, bottom=12),
        content=ft.Column(
            spacing=7,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=92,
                    height=92,
                    border_radius=24,
                    bgcolor="#ffffff",
                    border=ft.Border.all(1, "#b9eee4"),
                    padding=ft.Padding.all(8),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Image(
                        src="Icons/Xopilot-icon-apk.png",
                        width=74,
                        height=74,
                        fit=ft.BoxFit.CONTAIN,
                    ),
                ),
                ft.Text(
                    "Xopilot-NN+ AI+ 2.0",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color="#123b43",
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    "Чаты, материалы и AI · DenBroLiik",
                    size=11,
                    color="#47747a",
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
        ),
    )


def _info_chip(text: str) -> ft.Container:
    return ft.Container(
        bgcolor="#dff8f3",
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=10, vertical=7),
        content=ft.Text(text, size=11, color="#087f8c", text_align=ft.TextAlign.CENTER),
    )


def build_about_info() -> ft.Column:
    return ft.Column(
        width=ABOUT_WIDTH,
        spacing=10,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Text(
                "Автономный рабочий интерфейс для чатов, материалов "
                "и локальной модели ИИ.",
                width=TEXT_WIDTH,
                size=13,
                color="#123b43",
                max_lines=2,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Text(
                "Локальная модель и зашифрованная история помогают "
                "работать без обязательной зависимости от облака.",
                width=TEXT_WIDTH,
                size=11,
                color="#47747a",
                max_lines=2,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Container(width=TEXT_WIDTH, content=ft.Divider(height=1, color="#b9eee4")),
            ft.Row(
                width=TEXT_WIDTH,
                spacing=8,
                run_spacing=8,
                wrap=True,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    _info_chip("Версия 2.0.0"),
                    _info_chip("Python · Mojo · Rust"),
                    ft.Container(
                        bgcolor="#dff8f3",
                        border_radius=10,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                        content=ft.Row(
                            spacing=4,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.LOCK_OUTLINE, size=13, color="#087f8c"),
                                ft.Text("БД зашифрована локально", size=11, color="#087f8c"),
                            ],
                        ),
                    ),
                ],
            ),
            ft.Text(
                "Windows · Linux · Flet",
                width=TEXT_WIDTH,
                size=11,
                color="#47747a",
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Text(
                "Релиз: 1 февраля 2026 г. · Разработчик: DenBroLiik",
                width=TEXT_WIDTH,
                size=11,
                color="#47747a",
                text_align=ft.TextAlign.CENTER,
            ),
        ],
    )
