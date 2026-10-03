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
try:
    from .palette import color
except ImportError:
    from app.palette import color
import os
import io
import asyncio
from pathlib import Path
from PIL import Image


def image_preview(path):
        try:
                with Image.open(path) as image:
                        image.thumbnail((256, 256))
                        buffer = io.BytesIO()
                        image.convert("RGB").save(buffer, format="JPEG")
                        return buffer.getvalue()
        except (OSError, ValueError):
                return b""


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


def build_file_tile(file: ft.FilePickerFile) -> ft.Container:
        async def save_copy(e):
                picker = ft.FilePicker()
                try:
                        data = await asyncio.to_thread(Path(file.path).read_bytes)
                        path = await picker.save_file(dialog_title="Сохранить копию вложения", file_name=file.name,
                                                       src_bytes=data)
                        if path and not e.page.web:
                                await asyncio.to_thread(Path(path).write_bytes, data)
                except Exception as exc:
                        e.page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось сохранить файл: {exc}")))
        preview = (
                ft.Image(
                        src=image_preview(file.path),
                        width=42,
                        height=42,
                        fit=ft.BoxFit.COVER,
                        border_radius=12,
                )
                if is_image_file(file)
                else ft.Icon(file_icon(file), size=34, color=color("#087f8c"))
        )
        return ft.Container(
                tooltip=f"Сохранить копию: {file.name}",
                on_click=save_copy,
                ink=True,
                width=96,
                height=94,
                bgcolor=color("#dff8f3"),
                border=ft.Border.all(1, color("#7DEED5")),
                border_radius=16,
                padding=ft.Padding.all(5),
                content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=3,
                        controls=[
                                preview,
                                ft.Text(
                                        file.name,
                                        size=10,
                                        color=color("#123b43"),
                                        max_lines=1,
                                        text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Text(
                                        format_file_size(file.size),
                                        size=9,
                                        color=color("#47747a"),
                                ),
                        ],
                ),
        )


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
                tile = build_file_tile(file)
                tile_content = tile.content or ft.Container()
                tile.content = ft.Stack(
                        controls=[
                                tile_content,
                                ft.Container(
                                        alignment=ft.Alignment.TOP_RIGHT,
                                        content=ft.IconButton(
                                                icon=ft.Icons.CLOSE,
                                                icon_size=13,
                                                width=24,
                                                height=24,
                                                padding=0,
                                                tooltip="Удалить файл",
                                                icon_color=color("#087f8c"),
                                                on_click=lambda _, selected=file: on_remove(selected),
                                        ),
                                ),
                        ],
                )
                chips.append(tile)

        return ft.Row(
                visible=bool(chips),
                animate_opacity=180,
                spacing=6,
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                controls=chips,
        )
