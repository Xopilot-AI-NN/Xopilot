"""
Файл: /App/settings/abaut/info.py
Описание: __Блок информации__.
           Отображает версию, назначение приложения и разработчика.
"""

import flet as ft


def build_about_row() -> ft.Container:
    return ft.Container(
        height=62,
        padding=ft.padding.Padding.symmetric(horizontal=10, vertical=8),
        border_radius=10,
        content=ft.Row(
            spacing=11,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=36,
                    height=36,
                    border_radius=18,
                    bgcolor="#dff8f3",
                    alignment=ft.alignment.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.INFO_OUTLINE, size=19, color="#087f8c"),
                ),
                ft.Column(
                    expand=True,
                    spacing=2,
                    controls=[
                        ft.Text("Xopilot-NN+ AI+ 2.0", size=13, color="#123b43"),
                        ft.Text("Чаты, материалы и AI · DenBroLiik", size=11, color="#47747a"),
                    ],
                ),
            ],
        ),
    )


def _info_chip(text: str) -> ft.Container:
    return ft.Container(
        bgcolor="#dff8f3",
        border_radius=10,
        padding=ft.padding.Padding.symmetric(horizontal=10, vertical=7),
        content=ft.Text(text, size=11, color="#087f8c"),
    )


def build_about_info() -> ft.Column:
    return ft.Column(
        width=455,
        spacing=10,
        controls=[
            ft.Text(
                "Автономный рабочий интерфейс для чатов, материалов "
                "и локальной модели ИИ.",
                width=430,
                size=13,
                color="#123b43",
                max_lines=2,
            ),
            ft.Text(
                "Локальная модель и зашифрованная история помогают "
                "работать без обязательной зависимости от облака.",
                width=430,
                size=11,
                color="#47747a",
                max_lines=2,
            ),
            ft.Divider(height=1, color="#b9eee4"),
            ft.Row(
                spacing=8,
                wrap=True,
                controls=[
                    _info_chip("Версия 2.0.0"),
                    _info_chip("Python · Mojo · Rust"),
                    ft.Container(
                        bgcolor="#dff8f3",
                        border_radius=10,
                        padding=ft.padding.Padding.symmetric(horizontal=10, vertical=7),
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
            ft.Text("Windows · Linux · Flet", size=11, color="#47747a"),
            ft.Text("Релиз: 1 февраля 2026 г. · Разработчик: DenBroLiik", size=11, color="#47747a"),
        ],
    )