"""
Файл: /App/app/workspace_browser.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Единая панель настроек и библиотеки рабочих пространств.
"""
"""Saved workspaces with shared instructions and materials."""
import flet as ft
try:
    from .palette import color, modern_input, apply_palette
except ImportError:
    from app.palette import color
from .file_selection import pick_materials
from .library_browser import build_library_dialog
try:
    from ..services import workspaces
    from ..services.chat_store import list_chat_items
    from ..services.platforms import compact_layout
except ImportError:
    from services import workspaces
    from services.chat_store import list_chat_items
    from services.platforms import compact_layout


ICON_MAP = dict(zip(workspaces.ICONS, [ft.Icons.FOLDER_OUTLINED, ft.Icons.CODE, ft.Icons.MENU_BOOK, ft.Icons.SCIENCE, ft.Icons.BRUSH, ft.Icons.WORK_OUTLINE, ft.Icons.SCHOOL, ft.Icons.MUSIC_NOTE, ft.Icons.FLIGHT, ft.Icons.ROCKET_LAUNCH, ft.Icons.FAVORITE_BORDER, ft.Icons.LIGHTBULB_OUTLINE]))

def build_workspaces_dialog(page, on_select=None, on_changed=None, on_open_chat=None, on_create_chat=None):
    cards = ft.Column(spacing=8)
    feedback = ft.Text('Инструкции и материалы пространства доступны во всех его чатах.', size=12, color=color('#47747a'))
    width = max(240, min(600, page.width - 112)) if isinstance(page.width, (float, int)) else 600
    height = max(230, min(450, page.height - 180)) if isinstance(page.height, (float, int)) else 450

    def notify():
        if on_changed:
            on_changed()

    def open_workspace(identifier):
        try:
            if on_select is not None and on_select(identifier) is not True:
                return
            page.pop_dialog()
        except Exception as exc:
            feedback.value = str(exc)
            page.update()

    def edit_workspace(item=None):
        if item:
            page.show_dialog(build_workspace_settings(page, item['id'], on_changed=lambda: (notify(), render())))
            return
        if item:
            item = next(i for i in workspaces.list_workspaces() if i['id'] == item['id'])
        icon_choice = ft.Dropdown(label='Иконка проекта', value=item.get('icon', 'folder') if item else 'folder',
            options=[ft.DropdownOption(key=k, text=v, leading_icon=ICON_MAP[k]) for k, v in workspaces.ICONS.items()])
        field = ft.TextField(label='Название', value=item['name'] if item else '', autofocus=True,
                             color=color('#123b43'), bgcolor=color('#f3fffc'))
        instructions = ft.TextField(label='Инструкции для ИИ', multiline=True, min_lines=3, max_lines=6,
                                    value=item.get('instructions', '') if item else '', color=color('#123b43'),
                                    hint_text='Цель проекта, стиль ответов, важные условия', bgcolor=color('#f3fffc'))
        materials = [dict(m) for m in item.get('materials', [])] if item else []
        files_list = ft.Column(spacing=3)
        error = ft.Text('', color=color('#b3261e'), size=12)
        picker = ft.FilePicker()

        def render_files():
            def remove(material):
                materials.remove(material)
                render_files()
                page.update()
            files_list.controls = [ft.Row(controls=[
                ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, color=color('#087f8c')),
                ft.Text(m['name'], color=color('#123b43'), size=12, expand=True),
                ft.IconButton(icon=ft.Icons.CLOSE, tooltip='Убрать из пространства',
                              icon_color=color('#087f8c'), on_click=lambda _, material=m: remove(material)),
            ]) for m in materials]

        async def add_files(_):
            try:
                for file in await pick_materials(page, picker):
                    if not any(m['path'] == file.path for m in materials):
                        materials.append({'name': file.name, 'path': file.path})
                error.value = ''
                render_files()
            except Exception as exc:
                error.value = str(exc)
            page.update()

        def save(_):
            try:
                if item:
                    workspaces.update_workspace(item['id'], field.value or '', instructions.value or '', materials, icon=icon_choice.value)
                else:
                    workspaces.create_workspace(field.value or '', instructions.value or '', materials, icon=icon_choice.value)
            except Exception as exc:
                error.value = str(exc)
                page.update()
                return
            page.pop_dialog()
            notify()
            render()
            page.update()

        render_files()
        page.show_dialog(ft.AlertDialog(
            modal=True, bgcolor=color('#eafffa'), shape=ft.RoundedRectangleBorder(radius=18),
            title=ft.Text('Настройки пространства' if item else 'Новое пространство', color=color('#123b43')),
            content=ft.Column(width=width, height=min(height, 300 + min(3, len(materials))*40), horizontal_alignment=ft.CrossAxisAlignment.STRETCH, scroll=ft.ScrollMode.AUTO, spacing=12,
                              controls=[field, icon_choice, instructions,
                                        ft.Text('Общие материалы', color=color('#123b43')), files_list,
                                        ft.OutlinedButton(content='Добавить файлы', icon=ft.Icons.ATTACH_FILE, on_click=add_files), error]),
            actions=[ft.TextButton(content='Отмена', on_click=lambda _: page.pop_dialog()),
                     ft.FilledButton(content='Сохранить', on_click=save)],
        ))

    def workspace_home(item):
        chats = workspaces.filter_chats(list_chat_items(), item['id'])
        def open_chat(identifier):
            if on_select and on_select(item['id']) is not True:
                return
            page.pop_dialog()
            page.pop_dialog()
            if on_open_chat:
                on_open_chat(identifier)
        def new_chat(_):
            page.pop_dialog()
            page.pop_dialog()
            if on_create_chat:
                on_create_chat(item['id'])
        controls = [ft.Container(bgcolor=color('#f3fffc'), padding=12, border_radius=16, ink=True,
            on_click=lambda _, cid=cid: open_chat(cid),
            content=ft.Row(controls=[ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE, color=color('#087f8c')),
                ft.Column(expand=True, spacing=3, controls=[ft.Text(title, color=color('#123b43')),
                    ft.Text(subtitle, color=color('#47747a'), size=11)])])) for cid, title, subtitle, _ in chats]
        page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'), shape=ft.RoundedRectangleBorder(radius=22),
            title=ft.Text(item['name'], color=color('#123b43')),
            content=ft.Column(width=width, height=height, spacing=14, controls=[
                ft.Row(wrap=True, controls=[
                    ft.OutlinedButton(content='Работа с проектом',icon=ft.Icons.TERMINAL,
                        on_click=lambda _:__import__(__package__+'.project_browser',fromlist=['open_project']).open_project(page,item)),
                    ft.OutlinedButton(content='Настройки и материалы', icon=ft.Icons.TUNE, on_click=lambda _: edit_workspace(item))]),
                ft.Text('Чаты пространства', color=color('#47747a'), size=12),
                ft.ListView(expand=True, spacing=8, controls=controls or [ft.Text('Начните первый чат этого проекта', color=color('#47747a'))])]),
            actions=[ft.TextButton(content='Назад', on_click=lambda _: page.pop_dialog()),
                     ft.FilledButton(content='Новый чат', icon=ft.Icons.ADD_COMMENT_OUTLINED, on_click=new_chat)]))

    def confirm_remove(item):
        def remove(_):
            try:
                workspaces.delete_workspace(item['id'])
                page.pop_dialog()
                notify()
                render()
                page.update()
            except Exception as exc:
                feedback.value = str(exc)
                page.update()
        page.show_dialog(ft.AlertDialog(
            modal=True, bgcolor=color('#eafffa'), title=ft.Text('Удалить пространство?', color=color('#123b43')),
            content=ft.Text('Чаты и их сообщения сохранятся в общем списке. Инструкции и список общих материалов будут удалены.', color=color('#47747a')),
            actions=[ft.TextButton(content='Отмена', on_click=lambda _: page.pop_dialog()),
                     ft.FilledButton(content='Удалить', on_click=remove)],
        ))

    def render():
        selected = workspaces.selected_workspace()
        chats = list_chat_items()
        cards.controls = []
        for item in workspaces.list_workspaces():
            count = len(workspaces.filter_chats(chats, item['id']))
            details = f'{count} чатов' + (' · выбрано' if selected == item['id'] else '')
            if item.get('instructions'):
                details += ' · инструкции'
            if item.get('materials'):
                details += f" · {len(item['materials'])} файлов"
            actions = []
            if item['id'] != workspaces.DEFAULT:
                edit = lambda _, i=item: edit_workspace(i)
                library = lambda _, i=item: page.show_dialog(build_library_dialog(page, i['id'], on_changed=render))
                remove = lambda _, i=item: confirm_remove(i)
                if compact_layout(page.width):
                    actions = [ft.PopupMenuButton(tooltip='Действия пространства',
                        content=ft.Icon(ft.Icons.MORE_HORIZ, color=color('#087f8c')),
                        items=[ft.PopupMenuItem(content=ft.Text('Настройки пространства'), on_click=edit),
                               ft.PopupMenuItem(content=ft.Text('Удалить пространство'), on_click=remove)])]
                else:
                    actions = [ft.IconButton(icon=ft.Icons.TUNE, tooltip='Настройки пространства', icon_color=color('#087f8c'), on_click=edit),
                               ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip='Удалить пространство', icon_color=color('#c94b4b'), on_click=remove)]
            cards.controls.append(ft.Container(
                bgcolor=color('#dff8f3') if selected == item['id'] else color('#f3fffc'), padding=10, border_radius=14,
                content=ft.Row(controls=[
                    ft.Icon(ICON_MAP.get(item.get('icon'), ft.Icons.FOLDER_OUTLINED), color=color('#087f8c')),
                    ft.Container(expand=True, ink=True, on_click=lambda _, i=item: open_workspace(i['id']) if i['id'] == workspaces.DEFAULT else workspace_home(i),
                                 content=ft.Column(spacing=3, controls=[
                                     ft.Text(item['name'], color=color('#123b43'), weight=ft.FontWeight.W_600,
                                             max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                     ft.Text(details, size=11, color=color('#47747a'), max_lines=2,
                                             overflow=ft.TextOverflow.ELLIPSIS)
                                 ])),
                    *actions,
                ])))

    render()
    return ft.AlertDialog(
        modal=False, bgcolor=color('#eafffa'), shape=ft.RoundedRectangleBorder(radius=18),
        inset_padding=ft.Padding.symmetric(horizontal=24, vertical=22),
        content=ft.Column(width=width, height=height, spacing=14, controls=[
            ft.Row(controls=[ft.Text('Рабочие пространства', size=20, color=color('#123b43'), expand=True),
                             ft.IconButton(icon=ft.Icons.ADD, tooltip='Создать пространство', icon_color=color('#087f8c'),
                                           on_click=lambda _: edit_workspace())]), feedback,
            ft.ListView(expand=True, controls=[cards])]),
        actions=[ft.TextButton(content='Закрыть', on_click=lambda _: page.pop_dialog())],
    )


def build_workspace_settings(page, identifier, on_changed=None):
    """Общая панель: инструкции, оформление, разрешения и живая библиотека."""
    from .library_browser import build_library_content
    try:from ..services import project_tools
    except ImportError:from services import project_tools
    item = next(i for i in workspaces.list_workspaces() if i['id'] == identifier)
    width = min(780, max(240, (page.width or 1000)-72))
    height = min(680, max(310, (page.height or 850)-190))
    name = modern_input(ft.TextField(label='Название', value=item['name']))
    icon = modern_input(ft.Dropdown(label='Иконка', value=item.get('icon','folder'),
        options=[ft.DropdownOption(key=k,text=v,leading_icon=ICON_MAP[k]) for k,v in workspaces.ICONS.items()]))
    instructions = modern_input(ft.TextField(label='Инструкции для ИИ', value=item.get('instructions',''),
        multiline=True, min_lines=3, max_lines=6, hint_text='Цель проекта, стиль ответов, важные условия'))
    status = ft.Text('', size=12, color=color('#47747a'))
    heading = ft.Text('Пространство · '+item['name'],expand=True,max_lines=2)
    def save(_):
        try:
            # Библиотека сохраняется сразу; не перезаписываем её старым снимком формы.
            workspaces.update_workspace(identifier,name.value or '',instructions.value or '',icon=icon.value)
            status.value='Настройки сохранены'
            heading.value='Пространство · '+(name.value or '').strip()
            if on_changed:on_changed()
        except Exception as exc:status.value=str(exc)
        page.update()
    library=build_library_content(page,identifier,on_changed)
    library.width=None;library.height=None;library.expand=True
    overview=ft.Container(padding=16,border_radius=18,bgcolor=color('#f3fffc'),
        content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.STRETCH,spacing=12,controls=[ft.Row(wrap=True,controls=[
            ft.Container(width=max(220,width-240),content=name),ft.Container(width=180,content=icon)]),instructions,
            ft.Text('Инструкции и отмеченные материалы доступны ИИ во всех чатах пространства.',size=12,color=color('#47747a'))]))
    result=ft.AlertDialog(bgcolor=color('#eafffa'),shape=ft.RoundedRectangleBorder(radius=24),
        inset_padding=ft.Padding.symmetric(horizontal=18,vertical=20),
        title=ft.Row(controls=[ft.Icon(ICON_MAP.get(item.get('icon'),ft.Icons.FOLDER_OUTLINED),color=color('#087f8c')),
            heading]),
        content=ft.Column(width=width,height=height,spacing=14,controls=[
            ft.Column(height=min(300,height*.5),scroll=ft.ScrollMode.AUTO,controls=[overview]),
            ft.Text('Библиотека проекта',weight=ft.FontWeight.W_600),library,status]),
        actions=[ft.TextButton(content='Закрыть',on_click=lambda _:page.pop_dialog()),
                 ft.FilledButton(content='Сохранить настройки',on_click=save)])
    apply_palette(result)
    return result
