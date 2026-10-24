"""
Файл: /App/app/workspace/project_browser.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Компонент project_browser интерфейса Xopilot.
"""
"""Connect a device-local folder and inspect/edit project source files."""
import asyncio
import flet as ft
from ..theme.palette import color, modern_input
from ..menu.buttons.actions import action_button
try:
    from ...services import project_tools
    from ...services.paths import app_data_dir
    from ...services.platforms import is_android
except ImportError:
    from services import project_tools
    from services.paths import app_data_dir
    from services.platforms import is_android


def open_project(page,item):
    from .project_inspection import open_search,open_git
    identifier=item['id'];cfg=project_tools.settings(identifier)
    path=modern_input(ft.TextField(label='Папка проекта на этом устройстве',value=cfg.get('root',''),read_only=is_android()))
    rows=ft.ListView(height=min(280,max(120,(page.height or 800)-420)),spacing=6,build_controls_on_demand=True)
    file_items=[]
    query=modern_input(ft.TextField(hint_text='Найти файл по имени',prefix_icon=ft.Icons.SEARCH))
    connection=ft.Text('Папка не подключена',size=12,color=color('#47747a'))
    def render_files(_=None):
        needle=(query.value or '').strip().casefold()
        visible=[item for item in file_items if needle in item['path'].casefold()]
        rows.controls=[ft.Container(padding=12,border_radius=16,bgcolor=color('#f3fffc'),ink=True,
            on_click=lambda _,name=f['path']:page.run_task(editor,name),
            content=ft.Row(spacing=12,controls=[ft.Icon(ft.Icons.CODE_ROUNDED,color=color('#087f8c'),size=21),
                ft.Text(f['path'],expand=True,max_lines=2,overflow=ft.TextOverflow.ELLIPSIS,color=color('#123b43')),
                ft.Text(str(f['bytes'])+' Б',size=11,color=color('#47747a'))])) for f in visible]
        if not rows.controls:
            rows.controls=[ft.Container(padding=24,border_radius=20,bgcolor=color('#f3fffc'),content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,spacing=8,controls=[
                    ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED,size=30,color=color('#087f8c')),
                    ft.Text('Нет совпадений' if file_items else 'Здесь будут файлы проекта',color=color('#123b43')),
                    ft.Text('Измените запрос поиска' if file_items else 'Подключите папку или создайте первый файл',
                        text_align=ft.TextAlign.CENTER,size=12,color=color('#47747a'))]))]
        page.update()
    def clear_query(_):
        query.value='';render_files()
    query.suffix=ft.IconButton(ft.Icons.CLOSE_ROUNDED,tooltip='Очистить поиск',on_click=clear_query)
    query.on_change=render_files
    status=ft.Text('ИИ читает файлы только выбранной папки. Запись и запуск команд требуют подтверждения.',size=12,color=color('#47747a'))
    picker=ft.FilePicker()
    async def refresh():
        try:
            files=await asyncio.to_thread(project_tools.list_files,identifier)
            if not dialog.open:return
            file_items[:]=files;render_files()
            status.value=f'Файлов: {len(files)}. Разрешение папки действует только на этом устройстве.'
            connection.value='Подключено на этом устройстве'
            for button in tools.controls:button.disabled=False
        except Exception as exc:
            if not dialog.open:return
            status.value=str(exc);file_items.clear();render_files()
            ready=bool(project_tools.settings(identifier).get('enabled'))
            connection.value='Папка недоступна' if ready else 'Папка не подключена'
            for button in tools.controls:button.disabled=True
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
        from .project_editor import open_editor
        try:await open_editor(page,identifier,name,on_saved=refresh)
        except Exception as exc:status.value=str(exc);page.update()
    tools=ft.Row(wrap=True,spacing=8,run_spacing=8,controls=[
        action_button('Новый файл',icon=ft.Icons.NOTE_ADD_OUTLINED,secondary=True,on_click=lambda _:page.run_task(editor)),
        action_button('Поиск по коду',icon=ft.Icons.SEARCH,secondary=True,on_click=lambda _:open_search(page,identifier,editor)),
        *([] if is_android() else [action_button('Git',icon=ft.Icons.ACCOUNT_TREE_OUTLINED,secondary=True,on_click=lambda _:open_git(page,identifier))])])
    for button in tools.controls:button.disabled=not cfg.get('enabled')
    render_files()
    dialog=ft.AlertDialog(bgcolor=color('#eafffa'),title=ft.Text('Проект · '+item['name']),
        content=ft.Column(width=650,height=min(600,max(280,(page.height or 800)-200)),scroll=ft.ScrollMode.AUTO,spacing=16,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[ft.Container(padding=16,border_radius=24,bgcolor=color('#dff8f3'),content=ft.Column(spacing=12,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,controls=[
                ft.Row(spacing=12,controls=[ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED,color=color('#087f8c'),size=26),
                    ft.Column(expand=True,spacing=3,controls=[ft.Text('Рабочая папка',size=16,weight=ft.FontWeight.W_600,color=color('#123b43')),connection])]),
                path,ft.Row(wrap=True,spacing=8,run_spacing=8,controls=[action_button('Создать папку проекта' if is_android() else 'Подключить папку',on_click=connect),
                    *([] if is_android() or page.web else [action_button('Выбрать',secondary=True,on_click=browse)]),
                    action_button('Отключить',secondary=True,on_click=disconnect)])])),
                status,tools,query,rows,
                ft.ExpansionTile(title=ft.Text('Как работает доступ',size=14,color=color('#123b43')),controls=[
                    ft.Container(padding=12,content=ft.Text('Прочитанные файлы передаются выбранной модели; при API — её внешнему провайдеру. Не подключайте папки с секретами. '
                        'Команды доступны в Linux/Windows. Процесс запускается с вашими правами; это не изолированная среда. '
                        'Путь папки не переносится синхронизацией. Для переноса файлов добавьте их в библиотеку.',size=12,color=color('#47747a')))])]),
        actions=[ft.TextButton(content='Закрыть',on_click=lambda _:page.pop_dialog())])
    page.show_dialog(dialog)
    if cfg.get('enabled'):page.run_task(refresh)
