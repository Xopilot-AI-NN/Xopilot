"""
Файл: /App/app/chat/messages/message_navigation.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Поиск по чату и локальные закладки с переходом к исходному сообщению.
"""
import asyncio
from datetime import datetime
import flet as ft
from ...theme.palette import color,modern_input
try:
    from ....services import message_navigation as navigation
except ImportError:
    from services import message_navigation as navigation


def open_navigation(page,chat_id,on_jump,*,bookmarks=False):
    field=modern_input(ft.TextField(hint_text='Поиск в закладках' if bookmarks else 'Найти текст в этом чате',prefix_icon=ft.Icons.SEARCH,autofocus=not bookmarks))
    author=modern_input(ft.Dropdown(label='Автор',value='all',options=[ft.DropdownOption(key='all',text='Все сообщения'),ft.DropdownOption(key='user',text='Вы'),ft.DropdownOption(key='ai',text='ИИ')]))
    rows=ft.Column(spacing=8);status=ft.Text('',size=12,color=color('#47747a'))
    more=ft.TextButton(content='Показать ещё',visible=False)
    offset=0;revision=0;closed=False
    async def load(reset=True):
        nonlocal offset,revision
        revision+=1;mine=revision
        if reset:
            offset=0;more.visible=False;more.disabled=True
            await asyncio.sleep(.2)
        if closed or mine!=revision:return
        query=field.value or '';more.disabled=True
        try:
            result=await asyncio.to_thread(navigation.search,chat_id,query,bookmarks=bookmarks,offset=offset,role=None if author.value=='all' else author.value)
            if closed or mine!=revision:return
            if reset:rows.controls=[]
            for item in result['items']:
                async def jump(_,target=item):
                    nonlocal closed
                    closed=True;page.pop_dialog();await on_jump(target['chat_id'],target['message_id'])
                date=datetime.fromtimestamp(item['created_at']).strftime('%d.%m · %H:%M')
                rows.controls.append(ft.Container(padding=14,border_radius=18,bgcolor=color('#f3fffc'),on_click=jump,content=ft.Column(spacing=6,controls=[
                    ft.Text(('Вы' if item['role']=='user' else 'Zephyr')+' · '+date,size=11,color=color('#47747a')),
                    ft.Text(item['excerpt'],max_lines=4,overflow=ft.TextOverflow.ELLIPSIS,color=color('#123b43'))])))
            status.value=(f"Найдено: {result['total']}" if result['total'] else
                          'Подходящих закладок нет.' if bookmarks and (query.strip() or author.value!='all') else
                          'Закладок пока нет. Добавьте важное сообщение через его меню.' if bookmarks else
                          'Совпадений нет' if query.strip() else 'Введите слова из сообщения. Поиск охватывает всю сохранённую историю этого чата.')
            offset=result['next_offset'];more.visible=result['has_more']
        except Exception as exc:
            if closed or mine!=revision:return
            status.value=str(exc)
        more.disabled=False;page.update()
    async def changed(_):await load()
    async def next_page(_):await load(False)
    field.on_change=changed;author.on_select=changed;more.on_click=next_page
    def close(_):
        nonlocal closed
        closed=True;page.pop_dialog()
    def dismiss(_):
        nonlocal closed
        closed=True
    page.show_dialog(ft.AlertDialog(title=ft.Text('Закладки этого чата' if bookmarks else 'Поиск в чате'),bgcolor=color('#eafffa'),shape=ft.RoundedRectangleBorder(radius=24),
        content=ft.Column(width=560,height=min(540,max(240,(page.height or 800)-240)),spacing=12,scroll=ft.ScrollMode.AUTO,controls=[field,author,
            *([ft.Text('Закладки хранятся только на этом устройстве.',size=11,color=color('#47747a'))] if bookmarks else []),status,rows,more]),
        actions=[ft.FilledTonalButton(content='Закрыть',on_click=close)],on_dismiss=dismiss))
    page.run_task(load)
