"""
Файл: /App/app/workspace/project_inspection.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Показываю поиск по исходникам и Git-изменения без запуска команд пользователя.
"""
import asyncio
import flet as ft
from ..theme.palette import color,modern_input
try:
    from ...services import project_inspection as inspect
except ImportError:
    from services import project_inspection as inspect


def open_search(page,identifier,on_open):
    query=modern_input(ft.TextField(label='Текст в коде',autofocus=True))
    pattern=modern_input(ft.TextField(label='Файлы',value='*',hint_text='Например: *.py или src/*.rs'))
    rows=ft.Column(spacing=8);status=ft.Text('',size=12,color=color('#47747a'));offset=0;closed=False;criteria=None
    more=ft.TextButton(content='Показать ещё',visible=False);button=ft.FilledTonalButton(content='Найти')
    async def search(_=None,append=False):
        nonlocal offset,criteria
        if closed or button.disabled:return
        current=(query.value or '',pattern.value or '*')
        if current!=criteria:append=False
        if not append:offset=0;rows.controls=[]
        criteria=current
        button.disabled=True;more.disabled=True;query.disabled=True;pattern.disabled=True;page.update()
        try:
            result=await asyncio.to_thread(inspect.search,identifier,query.value or '',pattern=pattern.value or '*',offset=offset)
            if closed:return
            for item in result['matches']:
                async def open_file(_,path=item['path']):
                    nonlocal closed
                    closed=True;page.pop_dialog();await on_open(path)
                rows.controls.append(ft.Container(padding=12,border_radius=16,bgcolor=color('#f3fffc'),on_click=open_file,content=ft.Column(spacing=5,controls=[
                    ft.Text(item['path']+':'+str(item['line']),weight=ft.FontWeight.W_600,color=color('#087f8c')),
                    ft.Text(item['text'],font_family='monospace',size=12,color=color('#123b43'))])))
            offset=result['next_offset'];more.visible=result['has_more']
            status.value=f"Показано: {offset} · прочитано файлов: {result['scanned_files']} · пропущено: {result['skipped_files']}"
            if not result['matches'] and not append:status.value='Совпадений нет. Большие и двоичные файлы не читаются.'
        except Exception as exc:
            if closed:return
            status.value=str(exc)
        button.disabled=False;more.disabled=False;query.disabled=False;pattern.disabled=False;page.update()
    async def next_page(_):await search(append=True)
    def close(_):
        nonlocal closed
        closed=True;page.pop_dialog()
    def dismiss(_):
        nonlocal closed
        closed=True
    button.on_click=search;query.on_submit=search;more.on_click=next_page
    page.show_dialog(ft.AlertDialog(title=ft.Text('Поиск по коду'),bgcolor=color('#eafffa'),content=ft.Column(width=650,
        height=min(550,max(260,(page.height or 800)-240)),scroll=ft.ScrollMode.AUTO,spacing=12,controls=[query,pattern,button,status,rows,more]),
        actions=[ft.FilledTonalButton(content='Закрыть',on_click=close)],on_dismiss=dismiss))


def open_git(page,identifier):
    rows=ft.Column(spacing=8);status=ft.Text('Читаем Git-статус…',size=12,color=color('#47747a'));closed=False
    async def diff(path,mode):
        try:
            result=await asyncio.to_thread(inspect.git,identifier,mode,path=path)
            if closed:return
            text=result['diff'] or 'Изменений нет. Новый файл появится в Git diff после добавления в индекс.'
            if result['truncated']:text+='\n…Вывод сокращён.'
            page.show_dialog(ft.AlertDialog(title=ft.Text(('Подготовленные изменения · ' if mode=='staged_diff' else 'Рабочие изменения · ')+path),bgcolor=color('#eafffa'),
                content=ft.Column(width=760,height=min(560,max(260,(page.height or 800)-230)),scroll=ft.ScrollMode.AUTO,controls=[ft.Text(text,font_family='monospace',size=12,selectable=True)]),
                actions=[ft.FilledTonalButton(content='Закрыть',on_click=lambda _:page.pop_dialog())]))
        except Exception as exc:status.value=str(exc);page.update()
    async def refresh(_=None):
        try:
            result=await asyncio.to_thread(inspect.git,identifier)
            if closed:return
            status.value=result['branch']+' · изменённых путей: '+str(len(result['files']))+(' · список сокращён' if result['truncated'] else '')
            rows.controls=[]
            for item in result['files']:
                async def working(_,path=item['path']):await diff(path,'diff')
                async def staged(_,path=item['path']):await diff(path,'staged_diff')
                rows.controls.append(ft.Container(padding=12,border_radius=16,bgcolor=color('#f3fffc'),content=ft.Column(spacing=6,controls=[
                    ft.Text(item['status']+' · '+item['path'],font_family='monospace',color=color('#123b43')),
                    ft.Row(wrap=True,controls=[ft.TextButton(content='Рабочие изменения',on_click=working),ft.TextButton(content='Подготовленные',on_click=staged)])])))
            if not rows.controls:rows.controls=[ft.Text('Рабочая папка чистая.')]
            page.update()
        except Exception as exc:
            if not closed:status.value=str(exc);page.update()
    def close(_):
        nonlocal closed
        closed=True;page.pop_dialog()
    def dismiss(_):
        nonlocal closed
        closed=True
    page.show_dialog(ft.AlertDialog(title=ft.Text('Git проекта'),bgcolor=color('#eafffa'),content=ft.Column(width=650,
        height=min(550,max(260,(page.height or 800)-240)),scroll=ft.ScrollMode.AUTO,spacing=12,controls=[
            ft.Text('Только просмотр. Xopilot не добавляет файлы в индекс и не создаёт коммиты.',size=12,color=color('#47747a')),status,
            ft.FilledTonalButton(content='Обновить',icon=ft.Icons.REFRESH,on_click=refresh),rows]),
        actions=[ft.FilledTonalButton(content='Закрыть',on_click=close)],on_dismiss=dismiss))
    page.run_task(refresh)
