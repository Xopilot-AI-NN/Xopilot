"""
Файл: /App/app/files.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Объекты прикреплённых файлов__
        при активации add_material и выборе файла файл(ы)
        клеются сверху строки ввода 
        также к сообщению сверху его текста
"""

import flet as ft


def format_file_size(size: int) -> str:
        if size < 1024:
                return f"{size} Б"
        if size < 1024 * 1024:
                return f"{size / 1024:.1f} КБ"
        return f"{size / (1024 * 1024):.1f} МБ"


def build_file_attachments(
        files: list[ft.FilePickerFile], on_remove
) -> ft.Row:
        chips = []
        for file in files:
                chips.append(
                        ft.Container(
                                bgcolor="#dff8f3",
                                border=ft.border.Border.all(1, "#7DEED5"),
                                border_radius=12,
                                padding=ft.padding.Padding.only(left=10, right=4, top=5, bottom=5),
                                content=ft.Row(
                                        spacing=6,
                                        tight=True,
                                        controls=[
                                                ft.Icon(
                                                        ft.Icons.INSERT_DRIVE_FILE_OUTLINED,
                                                        size=17,
                                                        color="#087f8c",
                                                ),
                                                ft.Column(
                                                        spacing=0,
                                                        tight=True,
                                                        controls=[
                                                                ft.Text(file.name, size=12, color="#123b43", no_wrap=True),
                                                                ft.Text(
                                                                        format_file_size(file.size),
                                                                        size=10,
                                                                        color="#47747a",
                                                                ),
                                                        ],
                                                ),
                                                ft.IconButton(
                                                        icon=ft.Icons.CLOSE,
                                                        icon_size=15,
                                                        tooltip="Удалить файл",
                                                        icon_color="#087f8c",
                                                        on_click=lambda _, selected=file: on_remove(selected),
                                                ),
                                        ],
                                ),
                        )
                )

        return ft.Row(
                visible=bool(chips),
                spacing=6,
                scroll=ft.ScrollMode.AUTO,
                controls=chips,
        )


