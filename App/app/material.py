"""
Файл: /App/app/material.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Объекты прикреплённых файлов__
        при активации add_material и выборе файла файл(ы) или прикрепления цитаты из сообщения или ответ на сообщение
        клеются сверху строки ввода 
        также к сообщению сверху его текста
"""

import flet as ft
import os


def is_image_file(file: ft.FilePickerFile) -> bool:
        image_extensions = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}
        return bool(file.path and os.path.splitext(file.name)[1].lower() in image_extensions)


def file_icon(file: ft.FilePickerFile):
        extension = os.path.splitext(file.name)[1].lower()
        if extension == ".pdf":
                return ft.Icons.PICTURE_AS_PDF_OUTLINED
        if extension in {".doc", ".docx"}:
                return ft.Icons.DESCRIPTION_OUTLINED
        if extension in {".xls", ".xlsx", ".csv"}:
                return ft.Icons.TABLE_CHART_OUTLINED
        if extension in {".zip", ".rar", ".7z"}:
                return ft.Icons.FOLDER_ZIP_OUTLINED
        return ft.Icons.INSERT_DRIVE_FILE_OUTLINED


def format_file_size(size: int) -> str:
        if size < 1024:
                return f"{size} Б"
        if size < 1024 * 1024:
                return f"{size / 1024:.1f} КБ"
        return f"{size / (1024 * 1024):.1f} МБ"


def file_from_path(path: str) -> ft.FilePickerFile | None:
        if not os.path.isfile(path):
                return None
        return ft.FilePickerFile(
                id=hash(path),
                name=os.path.basename(path),
                size=os.path.getsize(path),
                path=path,
        )


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
                                                (
                                                        ft.Image(
                                                                src=file.path or "",
                                                                width=28,
                                                                height=28,
                                                                fit=ft.BoxFit.COVER,
                                                                border_radius=5,
                                                        )
                                                        if is_image_file(file)
                                                        else ft.Icon(
                                                                file_icon(file),
                                                                size=22,
                                                                color="#087f8c",
                                                        )
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
                animate_opacity=180,
                spacing=6,
                scroll=ft.ScrollMode.AUTO,
                controls=chips,
        )


