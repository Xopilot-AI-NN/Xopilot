"""
Файл: /App/app/materials/material_viewer.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Компонент material_viewer интерфейса Xopilot.
"""
"""Shared, responsive preview/export controls for storage and library."""
import asyncio
from pathlib import Path
import flet as ft
from ..theme.palette import color, apply_palette
try:
    from ...services import material_preview, storage
    from ...services.platforms import is_android, dialog_width, available_height
except ImportError:
    from services import material_preview, storage
    from services.platforms import is_android, dialog_width, available_height


async def export_material(page, path, name):
    source = await asyncio.to_thread(material_preview.resolve, path)
    name = Path(name.replace('\\', '/')).name
    if is_android() and not page.web:
        try:
            from ...services.mobile_documents import save_document_file
        except ImportError:
            from services.mobile_documents import save_document_file
        return await save_document_file(name, source)
    picker = ft.FilePicker()
    if page.web:
        if source.stat().st_size > material_preview.WEB_EXPORT_BYTES:
            raise ValueError('Этот файл большой для скачивания через браузер. Сохраните его из приложения Xopilot на ПК или телефоне')
        await picker.save_file(file_name=name, src_bytes=await asyncio.to_thread(source.read_bytes))
        return True
    destination = await picker.save_file(dialog_title='Сохранить копию материала', file_name=name)
    if destination:
        await asyncio.to_thread(material_preview.copy_to, source, destination)
        return True
    return False


async def open_material(page, path, name, *, references=None):
    data = await asyncio.to_thread(material_preview.preview, path, name)
    width = dialog_width(page, 720)
    height = max(180, min(560, (available_height(page) or 720) - 200))
    status = ft.Text('', size=12, color=color('#47747a'))
    contents = [ft.Text(storage.format_bytes(data['bytes']), size=12, color=color('#47747a'))]
    if references:
        contents.append(ft.Text('\n'.join(references), size=11, color=color('#47747a')))
    if data['image']:
        contents.append(ft.Image(src=data['image'], width=width, fit=ft.BoxFit.CONTAIN))
    if data['text']:
        contents.append(ft.Text(data['text'], selectable=True, color=color('#123b43')))
    if not data['image'] and not data['text']:
        contents.append(ft.Text('Файл пуст', color=color('#47747a')))
    if data['truncated']:
        contents.append(ft.Text('Показан фрагмент. Скачайте оригинал для полного просмотра.', size=11, color=color('#47747a')))
    async def save(_):
        button.disabled = True;status.value = 'Выберите место сохранения';page.update()
        try:
            status.value = 'Копия сохранена' if await export_material(page, path, name) else 'Сохранение отменено'
        except Exception as exc:
            status.value = str(exc)
        finally:
            button.disabled = False;page.update()
    button = ft.FilledButton(content='Скачать / сохранить', icon=ft.Icons.DOWNLOAD_OUTLINED, on_click=save)
    page.show_dialog(apply_palette(ft.AlertDialog(bgcolor=color('#eafffa'), title=ft.Text(name),
        content=ft.Column(width=width, height=height, controls=[ft.ListView(expand=True, controls=contents), status]),
        actions=[ft.TextButton(content='Закрыть', on_click=lambda _: page.pop_dialog()), button])))
