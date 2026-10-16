"""
Файл: /App/app/workspace/library_browser.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Поиск, просмотр и управление материалами пространства.
"""
"""Searchable library, with document preview, notes and folder import."""
import asyncio
from pathlib import Path
import flet as ft
from ..theme.palette import color, apply_palette
from ..materials.file_selection import pick_materials
from ..materials.material_viewer import open_material, export_material
try:
    from ...services import library, workspaces, project_tools
    from ...services.platforms import is_android
except ImportError:
    from services import library, workspaces,project_tools
    from services.platforms import is_android


def build_library_content(page, workspace_id, on_changed=None):
    item = next(item for item in workspaces.list_workspaces() if item['id'] == workspace_id)
    width = min(750, max(220, (page.width or 1000) - 112))
    height = min(560, max(300, (page.height or 760) - 180))
    search = ft.TextField(hint_text='Поиск в библиотеке', prefix_icon=ft.Icons.SEARCH)
    rows = ft.Column(spacing=8)
    folder_card=ft.Container(visible=False,padding=12,border_radius=16,bgcolor=color('#dff8f3'))
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
            await open_material(page,entry['path'],entry['name'])
        except Exception as exc:
            feedback.value = str(exc)
            page.update()

    async def save_copy(_,entry):
        try:
            saved=await export_material(page,entry['path'],entry['name'])
            feedback.value='Копия сохранена' if saved else 'Сохранение отменено'
        except Exception as exc:feedback.value=str(exc)
        page.update()

    def render(e=None):
        query = (search.value or '').casefold().strip()
        try:
            cfg=project_tools.settings(workspace_id) if workspace_id!=workspaces.DEFAULT else {}
            folder_card.visible=bool(cfg.get('enabled') and cfg.get('root'))
            if folder_card.visible:
                def open_project(_):
                    from .project_browser import open_project
                    current=next(w for w in workspaces.list_workspaces() if w['id']==workspace_id)
                    open_project(page,current)
                folder_card.content=ft.Column(spacing=5,controls=[
                    ft.Row(controls=[ft.Icon(ft.Icons.FOLDER_OPEN_OUTLINED,color=color('#087f8c')),
                        ft.Text('Папка проекта · '+Path(cfg['root']).name,expand=True),
                        ft.OutlinedButton(content='Открыть',on_click=open_project)]),
                    ft.Text(cfg['root'],size=11,selectable=True),
                    ft.Text('Файлы доступны ИИ на этом компьютере. Папка может быть пустой; её путь не синхронизируется.',size=11,color=color('#47747a'))])
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
                        ft.IconButton(icon=ft.Icons.DOWNLOAD_OUTLINED,tooltip='Скачать материал',icon_color=color('#087f8c'),
                            on_click=lambda e,entry=entry: page.run_task(save_copy,e,entry)),
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
            if is_android() and not page.web:
                try:
                    from ...services.mobile_documents import pick_workspace_documents
                except ImportError:
                    from services.mobile_documents import pick_workspace_documents
                result = await pick_workspace_documents(workspace_id)
                files = (result or {}).get('files', [])
            else:
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
        use = ft.Dropdown(label='Как использовать папку',value='project',
            options=[ft.DropdownOption(key='project',text='Папка проекта — можно начать с пустой'),
                     ft.DropdownOption(key='copies',text='Копии файлов в библиотеке')])
        error = ft.Text('Подключённая папка доступна ИИ для чтения и записи. Запись и команды подчиняются режиму подтверждения этого чата.',size=12,color=color('#47747a'))
        def mode_changed(_):
            button.content='Подключить папку' if use.value=='project' else 'Импортировать копии'
            error.value=('ИИ работает с настоящими файлами выбранной папки на этом компьютере. Пустая папка тоже подходит.'
                if use.value=='project' else 'В библиотеке сохраняются копии поддерживаемых файлов. Пустая папка не содержит материалов для копирования.')
            page.update()
        use.on_change=mode_changed
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
                if use.value=='project':
                    await asyncio.to_thread(project_tools.configure,workspace_id,path.value or '')
                    feedback.value='Папка подключена. Можно создавать первые файлы в чате проекта.'
                    page.pop_dialog();render()
                    if on_changed:on_changed()
                    page.update();return
                materials, errors = await asyncio.to_thread(library.import_folder, path.value or '')
                library.append_materials(workspace_id, materials)
                feedback.value = (f'Из папки добавлено файлов: {len(materials)}' if materials else 'Папка пуста или нет поддерживаемых файлов. Можно подключить её как папку проекта.') + (f' · ошибок: {len(errors)}' if errors else '')
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
        button = ft.FilledButton(content='Подключить папку', on_click=import_files)
        page.show_dialog(ft.AlertDialog(modal=True, bgcolor=color('#eafffa'), title=ft.Text('Добавить папку', color=color('#123b43')),
            content=ft.Column(width=min(width, 500), tight=True, controls=[path,use,
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
    return ft.Column(width=width, height=height, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, spacing=14, controls=[search,
            ft.Row(wrap=True, spacing=8, controls=[
                ft.OutlinedButton(content='Файлы', icon=ft.Icons.ATTACH_FILE, on_click=add_files),
                *([] if is_android() else [ft.OutlinedButton(content='Папка', icon=ft.Icons.CREATE_NEW_FOLDER_OUTLINED, on_click=folder_dialog)]),
                ft.OutlinedButton(content='Заметка', icon=ft.Icons.NOTE_ADD_OUTLINED, on_click=note_dialog)]),
            feedback,folder_card, ft.ListView(expand=True, controls=[rows])])


def build_library_dialog(page, workspace_id, on_changed=None):
    if workspace_id != workspaces.DEFAULT:
        from .workspace_browser import build_workspace_settings
        return build_workspace_settings(page, workspace_id, on_changed=on_changed)
    return ft.AlertDialog(bgcolor=color('#eafffa'), shape=ft.RoundedRectangleBorder(radius=22),
        title=ft.Text('Библиотека', color=color('#123b43')),
        content=build_library_content(page, workspace_id, on_changed),
        actions=[ft.TextButton(content='Закрыть', on_click=lambda _: page.pop_dialog())])
