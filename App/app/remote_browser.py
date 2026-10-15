"""
Файл: /App/app/remote_browser.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Задания телефон → ПК, состояния доставки и подтверждения внутри панели.
          Доступ разрешается только выбранным устройствам владельца.
"""
import asyncio
import json
import difflib
import flet as ft
from .palette import color,modern_input
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
    closed=False;current=None;shown_question=None;has_hosts=False;busy=False
    muted=color('#47747a')
    feedback=ft.Text('Ищем ваши компьютеры…',size=12,color=muted)
    indicator=ft.ProgressRing(width=16,height=16,stroke_width=2)
    host=modern_input(ft.Dropdown(label='Компьютер',expand=True,options=[]))
    scope=modern_input(ft.Dropdown(label='Пространство',value='all',expand=True,
        options=[ft.DropdownOption(key=w['id'],text='Обычный чат' if w['id']=='all' else w['name']) for w in workspaces.list_workspaces()]))
    prompt=modern_input(ft.TextField(label='Что нужно сделать на ПК?',hint_text='Например, проверить проект или создать документ',
        multiline=True,min_lines=3,max_lines=6))
    result=ft.Markdown('',selectable=True)
    approval_area=ft.Column(spacing=10,visible=False)
    host_controls=ft.Column(spacing=10,visible=not is_android())
    cancel=ft.TextButton(content='Отменить задание',icon=ft.Icons.CLOSE,visible=False)
    retry=ft.OutlinedButton(content='Проверить доставку',icon=ft.Icons.CLOUD_SYNC,visible=False)
    send=ft.FilledButton(content='Отправить на ПК',icon=ft.Icons.SEND,disabled=True)
    empty_hint=ft.Text('',size=12,expand=True)
    empty=ft.Container(padding=14,bgcolor=color('#eafffa'),border_radius=14,content=ft.Row(spacing=12,
        controls=[ft.Icon(ft.Icons.DEVICES_OUTLINED,color=color('#087f8c')),
            empty_hint]))
    def card(controls):
        return ft.Container(padding=16,border_radius=18,bgcolor=color('#ffffff'),
            border=ft.Border.all(1,color('#b9eee4')),content=ft.Column(spacing=12,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,controls=controls))
    selection=card([ft.Text('Задание на компьютере',size=15,weight=ft.FontWeight.W_600),host,scope,prompt,
        ft.Row(wrap=True,controls=[send,retry,cancel])])
    output=card([ft.Row(spacing=10,controls=[indicator,feedback]),result,approval_area])

    def update():
        if not closed:page.update()
    def active(value):
        nonlocal busy
        busy=value;send.disabled=value or not has_hosts;host.disabled=scope.disabled=value
        cancel.visible=value;indicator.visible=value

    def approval(identifier,question,request):
        title,preview=approval_content(request)
        status=ft.Text('',size=12,color=color('#c94b4b'))
        buttons=ft.Row(spacing=8,wrap=True)
        async def choose(value):
            buttons.disabled=True;update()
            try:
                await asyncio.to_thread(remote_tasks.decide,identifier,question,request,value)
                approval_area.visible=False
                feedback.value='Решение отправлено на ПК';update()
            except Exception as exc:status.value=str(exc);buttons.disabled=False;update()
        buttons.controls=[ft.TextButton(content='Отклонить',on_click=lambda _:page.run_task(choose,False)),
            ft.FilledButton(content='Разрешить это действие',on_click=lambda _:page.run_task(choose,True))]
        approval_area.controls=[ft.Divider(),ft.Text(title,weight=ft.FontWeight.W_600),
            ft.Text(request.get('cwd') or 'Подтверждение относится только к показанному действию.',size=12,color=muted),
            ft.Container(padding=12,border_radius=12,bgcolor=color('#eafffa'),
                content=ft.Text(preview,selectable=True,font_family='monospace',size=12)),status,buttons]
        approval_area.visible=True

    async def watch(identifier):
        nonlocal shown_question
        while not closed:
            try:
                row=await asyncio.to_thread(remote_tasks.inspect,identifier)
                details=row.get('decoded_result') or {}
                labels={'queued':'В очереди · ожидаем компьютер','running':'ИИ работает на компьютере',
                    'approval':'Нужно ваше разрешение','completed':'Задание выполнено','failed':'Задание завершилось с ошибкой',
                    'cancelled':'Задание отменено','expired':'Время ожидания истекло'}
                feedback.value=labels.get(row['state'],row['state'])
                result.value=details.get('reply') or details.get('error') or details.get('progress') or ''
                if details.get('files'):result.value+='\n\nФайлы: '+', '.join(details['files'])+'\n\nЧат и файлы появятся после синхронизации.'
                if row['state']=='approval' and row.get('question')!=shown_question:
                    shown_question=row['question'];approval(identifier,row['question'],details['request'])
                if row['state']!='approval':approval_area.visible=False
                if row['state'] in {'completed','failed','cancelled','expired'}:
                    active(False);update();return
                update()
            except Exception as exc:
                feedback.value='Восстанавливаем связь: '+str(exc);update()
            await asyncio.sleep(3)

    async def submit(_):
        nonlocal current,shown_question
        if not (prompt.value or '').strip():
            prompt.error_text='Опишите задание';update();return
        prompt.error_text=None;active(True);result.value='';shown_question=None;retry.visible=False;update()
        try:
            current=await asyncio.to_thread(remote_tasks.submit,host.value,prompt.value,scope.value)
            prompt.value='';page.run_task(watch,current)
        except remote_tasks.DeliveryPending as exc:
            current=exc.identifier;feedback.value=str(exc);retry.visible=True;indicator.visible=False
        except Exception as exc:
            feedback.value=str(exc);active(False)
        update()

    async def deliver(_):
        retry.disabled=True;feedback.value='Проверяем доставку того же задания…';update()
        try:
            await asyncio.to_thread(remote_tasks.retry,current)
            retry.visible=False;indicator.visible=True;page.run_task(watch,current)
        except Exception as exc:feedback.value=str(exc)
        finally:retry.disabled=False;update()

    async def stop(_):
        try:
            if current:await asyncio.to_thread(remote_tasks.cancel,current)
            retry.visible=False;approval_area.visible=False;feedback.value='Задание отменено';active(False)
        except Exception as exc:feedback.value=str(exc)
        update()
    send.on_click=submit;cancel.on_click=stop;retry.on_click=deliver

    async def refresh_hosts():
        nonlocal has_hosts
        if not is_android():
            await asyncio.to_thread(remote_tasks.start,guard=lambda:getattr(page,'_xopilot_can_sync',lambda:False)() and getattr(page,'_xopilot_can_release_model',lambda:False)())
        hosts=await asyncio.to_thread(remote_tasks.hosts)
        has_hosts=bool(hosts);keys={h['session_id'] for h in hosts}
        host.options=[ft.DropdownOption(key=h['session_id'],text=h['name']+(' · в сети' if h['online'] else ' · не в сети')) for h in hosts]
        if host.value not in keys:host.value=next((h['session_id'] for h in hosts if h['online']),hosts[0]['session_id'] if hosts else None)
        empty.visible=not has_hosts;selection.visible=has_hosts or busy
        send.disabled=busy or not has_hosts
        receiving=not is_android() and remote_tasks.options().get('enabled',False)
        empty_hint.value=('Откройте Xopilot на ПК и разрешите приём заданий от этого телефона.' if is_android() else
            'Приём включён. На телефоне откройте «Аккаунт → Подключение к ПК» и выберите этот компьютер.' if receiving else
            'Чтобы получать задания с телефона, отметьте его ниже и включите приём на этом ПК.')
        if not current:
            feedback.value=('Связь защищена сквозным шифрованием. Команды и изменения файлов требуют разрешения.' if hosts else
                'Этот компьютер готов принимать задания' if receiving else 'Выберите устройства для подключения')
        update()

    async def load():
        nonlocal current
        try:
            await refresh_hosts()
            pending=await asyncio.to_thread(remote_tasks.pending_deliveries)
            if pending:
                current=pending[-1];active(True);retry.visible=True;indicator.visible=False;selection.visible=True
                feedback.value='Осталось задание с неподтверждённой доставкой. Проверьте его перед новой отправкой.'
            if not is_android():
                config=remote_tasks.options();sessions=await asyncio.to_thread(cloud_account.sessions)
                boxes=[ft.Checkbox(label=s['device_name'],value=s['id'] in config.get('senders',[]),data=s['id']) for s in sessions if not s['current']]
                enabled=ft.Switch(label='Принимать задания на этом ПК',value=config.get('enabled',False))
                receiver_status=ft.Text('Разрешение действует только для отмеченных устройств.',size=12,color=muted)
                async def configure(_):
                    enabled.disabled=True;update()
                    try:
                        await asyncio.to_thread(remote_tasks.configure,enabled.value,[box.data for box in boxes if box.value],
                            guard=lambda:getattr(page,'_xopilot_can_sync',lambda:False)() and getattr(page,'_xopilot_can_release_model',lambda:False)())
                        receiver_status.value='Приём включён. Оставьте Xopilot открытым.' if enabled.value else 'Приём выключен'
                    except Exception as exc:
                        receiver_status.value=str(exc);enabled.value=remote_tasks.options().get('enabled',False)
                    finally:enabled.disabled=False;update()
                enabled.on_change=configure
                for box in boxes:box.on_change=configure
                host_controls.controls=[card([ft.Text('Этот компьютер',size=15,weight=ft.FontWeight.W_600),
                    ft.Text('Выберите устройства, которым разрешено присылать задания.',size=12,color=muted),
                    *(boxes or [ft.Text('Войдите в этот же аккаунт на телефоне — он появится здесь.',size=12,color=muted)]),
                    enabled,receiver_status])]
        except Exception as exc:feedback.value=str(exc)
        indicator.visible=busy and not retry.visible;update()
        while not closed:
            for _ in range(10):
                if closed:return
                await asyncio.sleep(1)
            try:await refresh_hosts()
            except Exception:
                if not busy:feedback.value='Нет связи с сервером · проверим снова автоматически';update()

    def dismissed(_):
        nonlocal closed
        closed=True
    def leave(_):
        dismissed(_);page.pop_dialog()
    page.show_dialog(ft.AlertDialog(title=ft.Text('Связь с компьютером'),bgcolor=color('#eafffa'),
        content=ft.Column(width=600,height=min(620,max(280,(page.height or 780)-190)),scroll=ft.ScrollMode.AUTO,spacing=14,
            controls=[ft.Text('Задания выполняются на выбранном ПК. Модель и файлы остаются на нём до синхронизации.',size=12,color=muted),
                host_controls,empty,selection,output,
                ft.Text('Закрытие панели не отменяет уже отправленное задание.',size=11,color=muted)]),
        actions=[ft.TextButton(content='Готово',on_click=leave)],on_dismiss=dismissed))
    page.run_task(load)
