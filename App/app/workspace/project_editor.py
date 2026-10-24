"""
Файл: /App/app/workspace/project_editor.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Редактирую файлы проекта с поиском, просмотром изменений и проверкой версии перед записью.
"""
import asyncio
import difflib
import re
import threading
import flet as ft
from ..theme.palette import color,modern_input
from ..theme.motion import switcher,panel
from ..menu.buttons.actions import action_button
try:
    from ...services import project_tools,library
    from ...services.material_store import store_material
except ImportError:
    from services import project_tools,library
    from services.material_store import store_material


def preview_diff(before,after,name):
    result=[];size=0
    for line in difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),
            fromfile='До / '+name,tofile='После / '+name):
        size+=len(line)
        if size>60000:return ''.join(result)+'\n…Предпросмотр сокращён. Сохраняется полный текст редактора.'
        result.append(line if line.endswith('\n') else line+'\n')
    return ''.join(result) or 'Изменений нет.'


async def open_editor(page,identifier,name=None,*,on_saved=None):
    baseline=await asyncio.to_thread(project_tools.read_file,identifier,name) if name else {'path':'','content':'','revision':'missing'}
    original_root=str(project_tools.root(identifier));busy=False;closed=False;position=0;previous_query=''
    filename=modern_input(ft.TextField(label='Путь внутри проекта',value=baseline['path'],read_only=bool(name)))
    code=modern_input(ft.TextField(value=baseline['content'],multiline=True,expand=True,fit_parent_size=True,text_vertical_align=-1,autocorrect=False,
        enable_suggestions=False,text_style=ft.TextStyle(font_family='monospace',size=13)))
    query=modern_input(ft.TextField(hint_text='Найти в файле',prefix_icon=ft.Icons.SEARCH,expand=True))
    status=switcher(page,ft.Text('Изменения ещё не сохранены' if not name else 'Файл открыт',key='opened',size=12,color=color('#47747a')))
    body_height=min(390,max(180,(page.height or 800)-360))
    editing=panel(page,key='edit',width=720,height=body_height,content=ft.Column(spacing=10,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,controls=[
        ft.Row(controls=[query,ft.IconButton(ft.Icons.FIND_IN_PAGE_OUTLINED,tooltip='Найти следующее',on_click=lambda _:page.run_task(find_next))]),code]))
    diff_text=ft.Text('',font_family='monospace',size=12,selectable=True,color=color('#123b43'))
    preview=panel(page,key='diff',width=720,height=body_height,opacity=0,ignore_interactions=True,
        bgcolor=color('#f3fffc'),border_radius=16,padding=12,
        content=ft.Column(scroll=ft.ScrollMode.AUTO,controls=[diff_text]))
    host=ft.Stack(width=720,height=body_height,controls=[editing,preview])
    def show_editing(value):
        editing.opacity=1 if value else 0;editing.ignore_interactions=not value
        preview.opacity=0 if value else 1;preview.ignore_interactions=value
        code.can_request_focus=value;query.can_request_focus=value

    metrics=ft.Text('',size=12,color=color('#47747a'))
    def notify(text,error=False):
        status.content=ft.Text(text,key=text,size=12,color=color('#b3261e' if error else '#47747a'))
    def dirty():return (code.value or '')!=baseline['content'] or (filename.value or '')!=baseline['path']
    def changed(_=None):
        nonlocal position,previous_query
        text=code.value or '';metrics.value=f"Строк: {len(text.splitlines()) or 1} · символов: {len(text)} · "+('Есть изменения' if dirty() else 'Сохранено')
        position=0;previous_query=''
        if _ is not None:page.update()
    code.on_change=changed;filename.on_change=changed
    async def find_next(_=None):
        nonlocal position,previous_query
        needle=query.value or ''
        if not needle:notify('Введите текст для поиска');page.update();return
        text=code.value or ''
        if needle!=previous_query:position=0;previous_query=needle
        expression=re.compile(re.escape(needle),re.IGNORECASE)
        hit=expression.search(text,position) or expression.search(text)
        if hit:
            position=hit.end()
            start=len(text[:hit.start()].encode('utf-16-le'))//2;end=len(text[:hit.end()].encode('utf-16-le'))//2
            code.selection=ft.TextSelection(base_offset=start,extent_offset=end)
            notify('Найдено · строка '+str(text.count('\n',0,hit.start())+1));page.update();await code.focus()
        else:notify('Совпадений нет');page.update()
    query.on_submit=find_next
    async def choose(e):
        if busy or closed:return
        if e.control.selected[0]=='edit':show_editing(True);code.read_only=False;page.update();return
        busy_state(True);notify('Сравниваю изменения…');page.update()
        try:
            text=await asyncio.to_thread(preview_diff,baseline['content'],code.value or '',filename.value or 'Новый файл')
            if closed:return
            diff_text.value=text;show_editing(False)
            notify('Сравнение с версией при открытии; исходный файл ещё не изменён')
        except Exception as exc:notify(str(exc),True)
        finally:
            busy_state(False)
            if not closed:page.update()
    tabs=ft.SegmentedButton(selected=['edit'],show_selected_icon=False,segments=[
        ft.Segment(value='edit',label='Код',icon=ft.Icons.CODE),ft.Segment(value='diff',label='Изменения',icon=ft.Icons.COMPARE_ARROWS)],on_change=choose)
    def busy_state(value):
        nonlocal busy
        busy=value;save_button.disabled=value;copy_button.disabled=value;tabs.disabled=value
        code.read_only=value or tabs.selected[0]=='diff';filename.read_only=bool(baseline['path']) or value
    async def save(_):
        if busy or closed:return
        busy_state(True);notify('Сохраняю…');page.update()
        try:
            if str(project_tools.root(identifier))!=original_root:raise ValueError('Папка проекта изменилась. Откройте файл заново')
            target=filename.value or '';text=code.value or ''
            await asyncio.to_thread(project_tools.write_file,identifier,target,text,threading.Event(),lambda _:True,expected_revision=baseline['revision'])
            baseline.update(path=target,content=text,revision=project_tools.file_revision(project_tools.resolve(identifier,target),text.encode('utf-8')))
            show_editing(True);tabs.selected=['edit'];changed();notify('Файл сохранён')
            if on_saved:await on_saved()
        except Exception as exc:notify(str(exc),True)
        finally:
            busy_state(False)
            if not closed:page.update()
    async def copy_to_library(_):
        if busy or closed:return
        busy_state(True);page.update()
        try:
            target=filename.value or ''
            if not target:raise ValueError('Укажите название файла')
            managed=await asyncio.to_thread(store_material,target,data=(code.value or '').encode())
            library.append_materials(identifier,[{'name':target,'path':managed,'enabled':True}])
            notify('Копия текущего текста добавлена в библиотеку')
        except Exception as exc:notify(str(exc),True)
        finally:busy_state(False);page.update()
    def close(_):
        nonlocal closed
        if busy:return
        if not dirty():closed=True;page.pop_dialog();return
        def discard(_):
            nonlocal closed
            closed=True;page.pop_dialog();page.pop_dialog()
        page.show_dialog(ft.AlertDialog(modal=True,title=ft.Text('Закрыть без сохранения?'),
            content=ft.Text('Изменения в редакторе будут потеряны. Исходный файл сохранится.'),
            actions=[ft.TextButton('Продолжить редактирование',on_click=lambda _:page.pop_dialog()),ft.FilledButton('Не сохранять',on_click=discard)]))
    def dismissed(_):
        nonlocal closed
        closed=True
    save_button=action_button('Сохранить',icon=ft.Icons.SAVE_OUTLINED,on_click=save)
    copy_button=action_button('В библиотеку',secondary=True,on_click=copy_to_library)
    changed()
    page.show_dialog(ft.AlertDialog(modal=True,bgcolor=color('#eafffa'),title=ft.Text('Редактор проекта'),on_dismiss=dismissed,
        content=ft.Column(width=720,height=body_height+170,spacing=10,scroll=ft.ScrollMode.AUTO,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[filename,tabs,host,metrics,status]),
        actions=[ft.TextButton('Закрыть',on_click=close),copy_button,save_button]))
