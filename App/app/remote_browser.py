"""
Файл: /App/app/remote_browser.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Подключение телефона к ПК, отправка заданий и подтверждение точных действий.
"""
import asyncio
import json
import difflib
import flet as ft
from .palette import color
try:
    from ..services import remote_tasks,cloud_account,workspaces
    from ..services.platforms import is_android
except ImportError:
    from services import remote_tasks,cloud_account,workspaces
    from services.platforms import is_android


def approval_content(request):
    if request.get('kind')=='command':
        title='Запустить команду на ПК?';preview=json.dumps(request['argv'],ensure_ascii=False,indent=2)
    elif request.get('kind') in {'device','computer_session'}:
        title=request.get('title','Действие на ПК')
        preview=json.dumps(request.get('arguments',{}),ensure_ascii=False,indent=2)
    else:
        title='Изменить файл на ПК?' if request.get('exists') else 'Создать файл на ПК?'
        preview=''.join(difflib.unified_diff(request.get('before','').splitlines(True),request.get('after','').splitlines(True),
            fromfile=request.get('path','Файл'),tofile=request.get('path','Файл')))
    return title,preview


def open_remote(page):
    closed=False; current=None; shown_question=None
    feedback=ft.Text('Загружаем доступные ПК…',size=12,color=color('#47747a'))
    host=ft.Dropdown(label='Подключённый ПК',expand=True,options=[])
    scope=ft.Dropdown(label='Пространство на ПК',value='all',expand=True,
        options=[ft.DropdownOption(key=w['id'],text='Обычный чат' if w['id']=='all' else w['name']) for w in workspaces.list_workspaces()])
    prompt=ft.TextField(label='Задание для ИИ на ПК',multiline=True,min_lines=3,max_lines=8)
    result=ft.Text('',selectable=True,color=color('#123b43'))
    host_controls=ft.Column(spacing=10)
    cancel=ft.OutlinedButton(content='Отменить задание',visible=False)
    send=ft.FilledButton(content='Отправить на ПК',icon=ft.Icons.SEND,disabled=True)
    approval_active=False

    def approval(identifier,question,request):
        nonlocal approval_active
        approval_active=True
        title,preview=approval_content(request)
        status=ft.Text('',size=12,color=color('#c94b4b'))
        async def choose(value):
            nonlocal approval_active
            try:
                await asyncio.to_thread(remote_tasks.decide,identifier,question,request,value)
                page.pop_dialog();approval_active=False
            except Exception as exc:status.value=str(exc);page.update()
        def dismissed(_):
            nonlocal approval_active
            approval_active=False
        page.show_dialog(ft.AlertDialog(modal=True,title=ft.Text(title),bgcolor=color('#eafffa'),
            content=ft.Column(width=640,height=min(420,max(220,(page.height or 760)-230)),scroll=ft.ScrollMode.AUTO,
                controls=[ft.Text('Папка ПК: '+request.get('cwd',''),size=12),
                    ft.Text('Команда запускается с правами пользователя ПК. Подтверждение относится только к этому действию.',size=12),
                    ft.Text(preview,selectable=True,font_family='monospace',size=12),status]),
            actions=[ft.TextButton(content='Отклонить',on_click=lambda _:page.run_task(choose,False)),
                ft.FilledButton(content='Подтвердить',on_click=lambda _:page.run_task(choose,True))],on_dismiss=dismissed))

    async def watch(identifier):
        nonlocal shown_question
        while not closed:
            try:
                row=await asyncio.to_thread(remote_tasks.inspect,identifier)
                details=row.get('decoded_result') or {}
                labels={'queued':'В очереди на ПК','running':'ИИ работает на ПК','approval':'Ожидает вашего подтверждения',
                    'completed':'Задание выполнено','failed':'Ошибка задания','cancelled':'Задание отменено','expired':'Время задания истекло'}
                feedback.value=labels.get(row['state'],row['state'])
                result.value=details.get('reply') or details.get('error') or details.get('progress') or ''
                if details.get('files'):result.value+='\n\nСозданные файлы: '+', '.join(details['files'])+'\nФайлы и чат переносятся обычной сквозной синхронизацией.'
                if row['state']=='approval' and row.get('question')!=shown_question and not approval_active:
                    shown_question=row['question'];approval(identifier,row['question'],details['request'])
                page.update()
                if row['state'] in {'completed','failed','cancelled','expired'}:
                    send.disabled=False;cancel.visible=False;page.update();return
            except Exception as exc:
                feedback.value='Не удалось обновить состояние: '+str(exc);page.update()
            await asyncio.sleep(3)

    async def submit(_):
        nonlocal current,shown_question
        send.disabled=True;result.value='';shown_question=None;page.update()
        try:
            current=await asyncio.to_thread(remote_tasks.submit,host.value,prompt.value or '',scope.value)
            cancel.visible=True;prompt.value='';page.update();page.run_task(watch,current)
        except Exception as exc:
            feedback.value=str(exc);send.disabled=False;page.update()

    async def stop(_):
        try:
            if current:await asyncio.to_thread(remote_tasks.cancel,current)
        except Exception as exc:feedback.value=str(exc);page.update()
    send.on_click=submit;cancel.on_click=stop

    async def load():
        try:
            hosts=await asyncio.to_thread(remote_tasks.hosts)
            host.options=[ft.DropdownOption(key=h['session_id'],text=h['name']+(' · в сети' if h['online'] else ' · не в сети')) for h in hosts]
            send.disabled=not bool(hosts)
            host.value=next((h['session_id'] for h in hosts if h['online']),hosts[0]['session_id'] if hosts else None)
            feedback.value='Выберите ПК и отправьте задание. Запись и команды потребуют отдельного подтверждения.' if hosts else 'На ПК откройте этот раздел и разрешите задания от вашего телефона.'
            if not is_android():
                config=remote_tasks.options();sessions=await asyncio.to_thread(cloud_account.sessions)
                boxes=[ft.Checkbox(label=s['device_name'],value=s['id'] in config.get('senders',[]),data=s['id']) for s in sessions if not s['current']]
                async def configure(_):
                    try:
                        await asyncio.to_thread(remote_tasks.configure,enabled.value,[box.data for box in boxes if box.value],
                            guard=lambda:getattr(page,'_xopilot_can_sync',lambda:False)() and getattr(page,'_xopilot_can_release_model',lambda:False)())
                        feedback.value='Приём заданий включён' if enabled.value else 'Приём заданий отключён'
                    except Exception as exc:feedback.value=str(exc)
                    page.update()
                enabled=ft.Switch(label='Принимать задания на этом ПК',value=config.get('enabled',False))
                enabled.on_change=configure
                for box in boxes:box.on_change=configure
                host_controls.controls=[ft.Divider(),ft.Text('Разрешённые отправители',weight=ft.FontWeight.BOLD,color=color('#123b43')),
                    ft.Text('Выберите конкретные устройства. Доступа к ПК у остальных сеансов аккаунта не будет.',size=12,color=color('#47747a')),
                    *boxes,enabled]
        except Exception as exc:feedback.value=str(exc)
        if not closed:page.update()

    def leave(_):
        nonlocal closed
        closed=True;page.pop_dialog()
    def dismissed(_):
        nonlocal closed
        closed=True
    page.show_dialog(ft.AlertDialog(title=ft.Text('Подключение к ПК'),bgcolor=color('#eafffa'),
        content=ft.Column(width=640,height=min(560,max(280,(page.height or 780)-190)),scroll=ft.ScrollMode.AUTO,spacing=12,
            controls=[ft.Row(wrap=True,controls=[host,scope]),prompt,ft.Row(wrap=True,controls=[send,cancel]),feedback,result,host_controls]),
        actions=[ft.TextButton(content='Закрыть',on_click=leave)],on_dismiss=dismissed))
    page.run_task(load)
