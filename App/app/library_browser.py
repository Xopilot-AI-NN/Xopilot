"""Searchable library, with document preview, notes and folder import."""
import asyncio
from pathlib import Path
import flet as ft
from .palette import color, apply_palette
from .file_selection import pick_materials
try:
    from ..services import library, workspaces
except ImportError:
    from services import library, workspaces


def build_library_dialog(page, workspace_id, on_changed=None):
    item = next(item for item in workspaces.list_workspaces() if item['id'] == workspace_id)
    width = min(750, max(220, (page.width or 1000) - 112))
    height = min(560, max(300, (page.height or 760) - 180))
    search = ft.TextField(hint_text='Поиск в библиотеке', prefix_icon=ft.Icons.SEARCH)
    rows = ft.Column(spacing=8)
    feedback = ft.Text('Отмеченные материалы используются ИИ во всех чатах пространства.', size=12, color=color('#47747a'))
    picker = ft.FilePicker()

    def save_entries(items):
        current = next(i for i in workspaces.list_workspaces() if i['id'] == workspace_id)
        workspaces.update_workspace(workspace_id, current['name'], current.get('instructions', ''), items)
        if on_changed:
            on_changed()

    def use_entry(entry, enabled):
        try:
            materials = next(i for i in workspaces.list_workspaces() if i['id'] == workspace_id).get('materials', [])
            save_entries([{**m, 'enabled': enabled} if library.material_id(m) == entry['id'] else m for m in materials])
            render()
        except Exception as exc:
            feedback.value = str(exc)
        page.update()

    def remove_entry(entry):
        def remove(_):
            try:
                materials = next(i for i in workspaces.list_workspaces() if i['id'] == workspace_id).get('materials', [])
                save_entries([m for m in materials if library.material_id(m) != entry['id']])
                page.pop_dialog()
                render()
            except Exception as exc:
                feedback.value = str(exc)
            page.update()
        page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'), title=ft.Text('Убрать из библиотеки?', color=color('#123b43')),
            content=ft.Text('Файл перестанет использоваться в этом пространстве. Оригинал и вложения чатов сохранятся.', color=color('#47747a')),
            actions=[ft.TextButton(content='Отмена', on_click=lambda _: page.pop_dialog()),
                     ft.FilledButton(content='Убрать', on_click=remove)]))

    async def preview(entry):
        try:
            text, images = await asyncio.to_thread(library.read_entry, entry)
            contents = [ft.Text(text, selectable=True, color=color('#123b43'))] if text else []
            contents += [ft.Image(src=image, fit=ft.BoxFit.CONTAIN) for image in images]
            page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'), title=ft.Text(entry['name'], color=color('#123b43')),
                content=ft.ListView(width=width, height=height-60, controls=contents),
                actions=[ft.TextButton(content='Закрыть', on_click=lambda _: page.pop_dialog())]))
        except Exception as exc:
            feedback.value = str(exc)
            page.update()

    def render(e=None):
        query = (search.value or '').casefold().strip()
        try:
            items = [m for m in library.entries(workspace_id) if query in m['name'].casefold()]
            controls = []
            for entry in items:
                async def open_file(_, entry=entry):
                    await preview(entry)
                controls.append(ft.Container(bgcolor=color('#f3fffc'), border_radius=16, padding=10,
                    content=ft.Row(spacing=4, controls=[
                        ft.Checkbox(value=entry['enabled'], tooltip='Использовать для ИИ',
                            on_change=lambda e, entry=entry: use_entry(entry, e.control.value)),
                        ft.Container(expand=True, ink=True, on_click=open_file,
                            content=ft.Column(spacing=3, controls=[ft.Text(entry['name'], color=color('#123b43')),
                                ft.Text(f"{entry['type']} · {entry['size']/1024:.1f} КБ" +
                                        ('' if entry['available'] else ' · недоступен'), size=11, color=color('#47747a'))])),
                        *([ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, tooltip='Редактировать заметку',
                            icon_color=color('#087f8c'), on_click=lambda _, entry=entry: note_dialog(None, entry))]
                            if entry['type'] == 'Заметка' else []),
                        ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip='Убрать материал',
                            icon_color=color('#c94b4b'), on_click=lambda _, entry=entry: remove_entry(entry))])))
            rows.controls = controls or [ft.Text('Библиотека пуста' if not query else 'Материалы не найдены', color=color('#47747a'))]
            apply_palette(rows)
        except Exception as exc:
            feedback.value = str(exc)
        if e:
            page.update()
    search.on_change = render

    async def add_files(_):
        try:
            files = await pick_materials(page, picker)
            library.append_materials(workspace_id, [{'name': f.name, 'path': f.path, 'enabled': True} for f in files])
            feedback.value = f'Добавлено файлов: {len(files)}'
            render()
            if on_changed:
                on_changed()
        except Exception as exc:
            feedback.value = str(exc)
        page.update()

    def folder_dialog(_):
        path = ft.TextField(label='Папка на этом компьютере', hint_text='/home/user/project')
        error = ft.Text('Будут созданы копии поддерживаемых файлов с сохранением структуры названий.', size=12, color=color('#47747a'))
        async def browse(_):
            selected = await picker.get_directory_path(dialog_title='Добавить папку в библиотеку')
            if selected:
                path.value = selected
                page.update()
        async def import_files(_):
            button.disabled = True
            error.value = 'Копирую материалы…'
            page.update()
            try:
                materials, errors = await asyncio.to_thread(library.import_folder, path.value or '')
                library.append_materials(workspace_id, materials)
                feedback.value = f'Из папки добавлено файлов: {len(materials)}' + (f' · ошибок: {len(errors)}' if errors else '')
                if errors:
                    error.value = '\n'.join(errors)
                    button.disabled = False
                    render()
                else:
                    page.pop_dialog()
                    render()
                if on_changed:
                    on_changed()
            except Exception as exc:
                error.value = str(exc)
                button.disabled = False
            page.update()
        button = ft.FilledButton(content='Импортировать', on_click=import_files)
        page.show_dialog(ft.AlertDialog(modal=True, bgcolor=color('#eafffa'), title=ft.Text('Добавить папку', color=color('#123b43')),
            content=ft.Column(width=min(width, 500), tight=True, controls=[path,
                *([ft.OutlinedButton(content='Выбрать папку', icon=ft.Icons.FOLDER_OPEN, on_click=browse)] if not page.web else []), error]),
            actions=[ft.TextButton(content='Закрыть', on_click=lambda _: page.pop_dialog()), button]))

    def note_dialog(_, entry=None):
        title = ft.TextField(label='Название заметки', value=Path(entry['name']).stem if entry else '', autofocus=True)
        body = ft.TextField(label='Текст', multiline=True, min_lines=5, max_lines=12,
                            value=Path(entry['path']).read_text(encoding='utf-8') if entry else '')
        error = ft.Text('', color=color('#b3261e'))
        def save(_):
            try:
                if entry:
                    library.update_note(workspace_id, entry['id'], title.value or '', body.value or '')
                else:
                    library.append_materials(workspace_id, [library.add_note(title.value or '', body.value or '')])
                page.pop_dialog()
                render()
                if on_changed:
                    on_changed()
            except Exception as exc:
                error.value = str(exc)
            page.update()
        page.show_dialog(ft.AlertDialog(modal=True, bgcolor=color('#eafffa'), title=ft.Text('Редактировать заметку' if entry else 'Новая заметка', color=color('#123b43')),
            content=ft.Column(width=min(width, 500), tight=True, controls=[title, body, error]),
            actions=[ft.TextButton(content='Отмена', on_click=lambda _: page.pop_dialog()),
                     ft.FilledButton(content='Сохранить' if entry else 'Добавить', on_click=save)]))
    render()
    return ft.AlertDialog(bgcolor=color('#eafffa'), shape=ft.RoundedRectangleBorder(radius=22),
        title=ft.Text('Библиотека · ' + item['name'], color=color('#123b43')),
        content=ft.Column(width=width, height=height, spacing=14, controls=[search,
            ft.Row(wrap=True, spacing=8, controls=[
                ft.OutlinedButton(content='Файлы', icon=ft.Icons.ATTACH_FILE, on_click=add_files),
                ft.OutlinedButton(content='Папка', icon=ft.Icons.CREATE_NEW_FOLDER_OUTLINED, on_click=folder_dialog),
                ft.OutlinedButton(content='Заметка', icon=ft.Icons.NOTE_ADD_OUTLINED, on_click=note_dialog)]),
            feedback, ft.ListView(expand=True, controls=[rows])]),
        actions=[ft.TextButton(content='Закрыть', on_click=lambda _: page.pop_dialog())])
