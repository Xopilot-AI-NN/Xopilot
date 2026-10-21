"""
Файл: /App/app/chat/composer/prompt_templates.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Управляю шаблонами и подставляю инструкции в черновик без автоматической отправки.
"""
import flet as ft
from ...theme.palette import color,modern_input
try:
    from ....services import prompt_templates as store
except ImportError:
    from services import prompt_templates as store


def open_editor(page,*,item=None,body='',on_saved=lambda:None):
    title=modern_input(ft.TextField(label='Название',value=item['title'] if item else (body.splitlines()[0][:60] if body else ''),max_length=80,autofocus=True))
    text=modern_input(ft.TextField(label='Текст запроса',value=item['body'] if item else body,multiline=True,min_lines=4,max_lines=9,max_length=20000))
    error=ft.Text('',color=color('#b3261e'),size=12)
    def save(_):
        try:
            store.save(title.value or '',text.value or '',item['id'] if item else None)
            page.pop_dialog();on_saved();page.update()
        except Exception as exc:error.value=str(exc);page.update()
    page.show_dialog(ft.AlertDialog(title=ft.Text('Изменить шаблон' if item else 'Новый шаблон'),bgcolor=color('#eafffa'),shape=ft.RoundedRectangleBorder(radius=24),
        content=ft.Column(width=520,tight=True,scroll=ft.ScrollMode.AUTO,controls=[title,text,error]),
        actions=[ft.TextButton(content='Отмена',on_click=lambda _:page.pop_dialog()),ft.FilledButton(content='Сохранить',on_click=save)]))


def open_templates(page,on_apply):
    query=modern_input(ft.TextField(hint_text='Найти шаблон',prefix_icon=ft.Icons.SEARCH))
    rows=ft.Column(spacing=10);status=ft.Text('',size=12,color=color('#47747a'))
    def refresh(_=None):
        try:
            items=store.list_templates(query.value or '');rows.controls=[]
            for item in items:
                async def apply(_,identifier=item['id']):
                    # Перед вставкой перечитываю запись: открытый список может устареть.
                    current=next((r for r in store.list_templates() if r['id']==identifier),None)
                    if current is None:status.value='Шаблон уже удалён';refresh();return
                    page.pop_dialog();await on_apply(current['body'])
                def edit(_,value=item):open_editor(page,item=value,on_saved=refresh)
                def remove(_,identifier=item['id']):
                    error=ft.Text('',size=12,color=color('#b3261e'))
                    def confirmed(_):
                        try:store.delete(identifier);page.pop_dialog();refresh()
                        except Exception as exc:error.value=str(exc);page.update()
                    page.show_dialog(ft.AlertDialog(title=ft.Text('Удалить шаблон?'),bgcolor=color('#eafffa'),content=ft.Column(tight=True,controls=[ft.Text('Сообщения, отправленные по этому шаблону, сохранятся.'),error]),
                        actions=[ft.TextButton(content='Отмена',on_click=lambda _:page.pop_dialog()),ft.FilledButton(content='Удалить',on_click=confirmed)]))
                rows.controls.append(ft.Container(padding=14,border_radius=20,bgcolor=color('#f3fffc'),content=ft.Column(spacing=8,controls=[
                    ft.Text(item['title'],weight=ft.FontWeight.W_600,color=color('#123b43')),
                    ft.Text(item['body'],max_lines=3,overflow=ft.TextOverflow.ELLIPSIS,color=color('#47747a'),size=12),
                    ft.Row(wrap=True,controls=[ft.FilledTonalButton(content='Вставить',on_click=apply),
                        ft.IconButton(icon=ft.Icons.EDIT_OUTLINED,tooltip='Изменить шаблон',on_click=edit),
                        ft.IconButton(icon=ft.Icons.DELETE_OUTLINE,tooltip='Удалить шаблон',on_click=remove)])])))
            status.value=('Ничего не найдено' if query.value else 'Сохраните часто используемые инструкции кнопкой «Создать».') if not items else f'Шаблонов: {len(items)}'
        except Exception as exc:status.value=str(exc)
        page.update()
    query.on_change=refresh
    page.show_dialog(ft.AlertDialog(title=ft.Text('Мои шаблоны'),bgcolor=color('#eafffa'),shape=ft.RoundedRectangleBorder(radius=24),
        content=ft.Column(width=560,height=min(550,max(250,(page.height or 800)-240)),scroll=ft.ScrollMode.AUTO,spacing=12,controls=[
            ft.Text('На этом устройстве · текст добавляется к черновику, отправка — вручную.',size=12,color=color('#47747a')),
            query,ft.FilledTonalButton(content='Создать',icon=ft.Icons.ADD,on_click=lambda _:open_editor(page,on_saved=refresh)),status,rows]),
        actions=[ft.FilledTonalButton(content='Закрыть',on_click=lambda _:page.pop_dialog())]))
    refresh()
