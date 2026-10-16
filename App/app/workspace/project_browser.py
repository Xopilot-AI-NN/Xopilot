"""
Файл: /App/app/workspace/project_browser.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Компонент project_browser интерфейса Xopilot.
"""
"""Connect a device-local folder and inspect/edit project source files."""
import asyncio
import json
from pathlib import Path
import threading
import flet as ft
from ..theme.palette import color, modern_input
from ..menu.buttons.actions import action_button
try:
    from ...services import project_tools, library
    from ...services.paths import app_data_dir
    from ...services.platforms import is_android
except ImportError:
    from services import project_tools,library
    from services.paths import app_data_dir
    from services.platforms import is_android


def open_project(page,item):
    identifier=item['id'];cfg=project_tools.settings(identifier)
    path=modern_input(ft.TextField(label='Папка проекта на этом устройстве',value=cfg.get('root',''),read_only=is_android()))
    rows=ft.ListView(height=280,spacing=6,build_controls_on_demand=True)
    status=ft.Text('ИИ читает файлы только выбранной папки. Запись и запуск команд требуют подтверждения.',size=12,color=color('#47747a'))
    picker=ft.FilePicker()
    async def refresh():
        try:
            files=await asyncio.to_thread(project_tools.list_files,identifier)
            rows.controls=[ft.Container(padding=10,border_radius=12,bgcolor=color('#f3fffc'),ink=True,
                on_click=lambda _,name=f['path']:page.run_task(editor,name),
                content=ft.Row(controls=[ft.Icon(ft.Icons.DESCRIPTION_OUTLINED,color=color('#087f8c')),
                    ft.Text(f['path'],expand=True,color=color('#123b43')),ft.Text(str(f['bytes'])+' Б',size=11,color=color('#47747a'))])) for f in files]
            status.value=f'Файлов: {len(files)}. Разрешение папки действует только на этом устройстве.'
        except Exception as exc:status.value=str(exc);rows.controls=[]
        page.update()
    async def connect(_):
        try:
            if is_android():
                folder=app_data_dir()/'projects'/identifier;folder.mkdir(parents=True,exist_ok=True);path.value=str(folder)
            await asyncio.to_thread(project_tools.configure,identifier,path.value or '')
            await refresh()
        except Exception as exc:status.value=str(exc);page.update()
    async def browse(_):
        try:
            selected=await picker.get_directory_path(dialog_title='Выбрать папку проекта')
            if selected:path.value=selected;await connect(None)
        except Exception as exc:status.value=str(exc);page.update()
    async def disconnect(_):
        await asyncio.to_thread(project_tools.configure,identifier,'',False)
        path.value='';await refresh()
    async def editor(name=None):
        try:data=await asyncio.to_thread(project_tools.read_file,identifier,name) if name else {'path':'','content':''}
        except Exception as exc:status.value=str(exc);page.update();return
        filename=modern_input(ft.TextField(label='Путь внутри проекта',value=data['path'],read_only=bool(name)))
        code=modern_input(ft.TextField(value=data['content'],multiline=True,min_lines=7,max_lines=16,text_style=ft.TextStyle(font_family='monospace')))
        error=ft.Text('',size=12)
        async def save(_):
            try:
                await asyncio.to_thread(project_tools.write_file,identifier,filename.value or '',code.value or '',threading.Event(),lambda _:True)
                page.pop_dialog();await refresh()
            except Exception as exc:error.value=str(exc);page.update()
        async def add_library(_):
            try:
                from ...services.material_store import store_material
            except ImportError:
                from services.material_store import store_material
            try:
                managed=await asyncio.to_thread(store_material,filename.value or '',data=(code.value or '').encode())
                library.append_materials(identifier,[{'name':filename.value,'path':managed,'enabled':True}])
                error.value='Копия добавлена в библиотеку и будет синхронизироваться как материал'
            except Exception as exc:error.value=str(exc)
            page.update()
        page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'),title=ft.Text('Файл проекта'),
            content=ft.Column(width=650,height=min(500,max(260,(page.height or 800)-220)),scroll=ft.ScrollMode.AUTO,
                              controls=[filename,code,error]),
            actions=[ft.TextButton(content='Закрыть',on_click=lambda _:page.pop_dialog()),
                     action_button('В библиотеку',secondary=True,on_click=add_library),action_button('Сохранить файл',on_click=save)]))
    page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'),title=ft.Text('Работа с проектом · '+item['name']),
        content=ft.Column(width=650,height=min(560,max(280,(page.height or 800)-200)),scroll=ft.ScrollMode.AUTO,spacing=12,
            controls=[path,ft.Row(wrap=True,controls=[action_button('Создать папку проекта' if is_android() else 'Подключить папку',on_click=connect),
                *([] if is_android() or page.web else [action_button('Выбрать',secondary=True,on_click=browse)]),
                action_button('Отключить',secondary=True,on_click=disconnect)]),status,
                action_button('Новый файл',icon=ft.Icons.NOTE_ADD_OUTLINED,secondary=True,on_click=lambda _:page.run_task(editor)),rows,
                ft.Text('Прочитанные файлы передаются выбранной модели; при API — её внешнему провайдеру. Не подключайте папки с секретами. '
                        'Команды доступны в Linux/Windows. Процесс запускается с вашими правами; это не изолированная среда. '
                        'Путь папки не переносится синхронизацией. Для переноса файлов добавьте их в библиотеку.',size=11,color=color('#47747a'))]),
        actions=[ft.TextButton(content='Закрыть',on_click=lambda _:page.pop_dialog())]))
    if cfg.get('enabled'):page.run_task(refresh)
