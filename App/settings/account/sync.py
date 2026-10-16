"""
Файл: /App/settings/account/sync.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Параметры синхронизации с живым состоянием передачи и повторов.
"""
import asyncio
import base64
from datetime import datetime
from decimal import Decimal
import flet as ft
try:
    from ...services import cloud_sync as sync, cloud_traffic
    from ...services.storage import format_bytes
    from ...app.theme.palette import color, modern_input
    from ...app.menu.buttons.actions import action_button
except ImportError:
    from services import cloud_sync as sync, cloud_traffic
    from services.storage import format_bytes
    from app.theme.palette import color, modern_input
    from app.menu.buttons.actions import action_button


def open_sync(page):
    options=sync.options()
    status=ft.Text('',size=12,color=color('#47747a'))
    enabled=ft.Switch(label='Синхронизация включена',value=options['enabled'])
    auto=ft.Switch(label='Автосинхронизация',value=options['auto'])
    traffic=ft.Switch(label='Ограничить отправку данных',value=options['traffic_limit'])
    limit=modern_input(ft.TextField(label='Лимит за последние 24 часа, МБ',value=str(options['daily_limit_bytes']/1024/1024),keyboard_type=ft.KeyboardType.NUMBER))
    categories={'profile':'Профиль и память обо мне','chats':'Чаты','workspaces':'Рабочие пространства','canvases':'Canvas','materials':'Материалы обычных чатов и проектов','protected':'Защищённые чаты с их вложениями'}
    checks={key:ft.Checkbox(label=label,value=options[key]) for key,label in categories.items()}
    preset=modern_input(ft.Dropdown(label='Что синхронизировать',value='custom',options=[
        ft.DropdownOption(key=key,text=text) for key,text in [('custom','Мой выбор'),('all','Всё'),('chats','Только чаты'),('workspaces','Только рабочие пространства'),('protected','Только защищённые чаты')]]))
    manual=action_button('Синхронизировать',icon=ft.Icons.SYNC)
    setup=action_button('Пароль синхронизации',icon=ft.Icons.KEY_OUTLINED,secondary=True)
    forget=ft.TextButton(content='Забыть ключ на этом устройстве')
    conflicts=action_button('Разобрать конфликты',secondary=True)

    def refresh():
        result=sync.status();used=cloud_traffic.usage(sync.owner())
        text='Ключ на устройстве сохранён' if sync.key_ready() else 'Задайте отдельный пароль для шифрования облачных данных'
        if result.get('last_sync'):text+='\nПоследняя синхронизация: '+datetime.fromtimestamp(result['last_sync']).strftime('%d.%m.%Y %H:%M')
        if result.get('last_sync'):text+=f"\nОтправлено изменений: {result.get('sent',0)} · получено: {result.get('received',0)}"
        if result.get('running'):text+='\n'+result.get('phase','Идёт синхронизация…')
        if result.get('error'):text+='\n'+result['error']
        if result.get('next_retry') and result.get('error'):
            text+='\nПовторим автоматически в '+datetime.fromtimestamp(result['next_retry']).strftime('%H:%M:%S')
        text+='\nОтправлено за 24 часа: '+format_bytes(used)
        status.value=text
        conflict_count=len(sync.conflict_items())
        conflicts.visible=bool(conflict_count)
        if conflict_count:text+=f'\nКонфликтов: {conflict_count}. Выберите версии — данные сохранены.'
        status.value=text
        manual.disabled=bool(result.get('running')) or not enabled.value or not sync.key_ready()

    def save(key,value):
        try:
            sync.save_options({key:value})
            if key in checks:preset.value='custom'
            status.value='Настройки сохранены';refresh()
            if enabled.value and sync.key_ready() and value and (key in ('enabled','auto') or (key in checks and auto.value)):
                page.run_task(synchronize,None)
        except Exception as exc:
            status.value=str(exc)
            options=sync.options()
            enabled.value=options['enabled'];auto.value=options['auto'];traffic.value=options['traffic_limit']
            for name,control in checks.items():control.value=options[name]
        page.update()

    def enable_sync(_):
        if enabled.value and not sync.key_ready():
            enabled.value=False
            password_dialog(enable_after=True)
            page.update()
        else:save('enabled',enabled.value)
    enabled.on_change=enable_sync
    auto.on_change=lambda _:save('auto',auto.value)
    traffic.on_change=lambda _:save('traffic_limit',traffic.value)
    for key,control in checks.items():
        control.on_change=lambda _,name=key,field=control:save(name,field.value)

    def apply_preset(_):
        if preset.value=='custom':return
        values={key:preset.value=='all' or key==preset.value for key in checks}
        values['profile']=True
        if preset.value in ('chats','workspaces'):values['materials']=True
        try:
            sync.save_options(values)
            for key,control in checks.items():control.value=values[key]
            refresh()
            if enabled.value and sync.key_ready():page.run_task(synchronize,None)
        except Exception as exc:status.value=str(exc)
        page.update()
    preset.on_select=apply_preset

    def save_limit(_):
        try:
            value=Decimal((limit.value or '').replace(',','.'))
            if not value.is_finite():raise ValueError('Введите число')
            if not Decimal(1)/1024<=value<=1024*1024:raise ValueError('Допустимый лимит: от 1 КБ до 1 ТБ')
            limit.error_text=None
            save('daily_limit_bytes',int(value*1024*1024))
        except Exception as exc:limit.error_text=str(exc);page.update()
    pending_limit=None
    async def limit_changed(_):
        nonlocal pending_limit
        if pending_limit:pending_limit.cancel()
        async def delayed_save():
            await asyncio.sleep(0.5)
            if dialog.open:save_limit(None)
        pending_limit=page.run_task(delayed_save)
    limit.on_change=limit_changed
    limit.on_submit=save_limit
    limit.on_blur=save_limit
    def flush_limit(_):
        if pending_limit:pending_limit.cancel()
        save_limit(None)
    def close(_):
        flush_limit(None)
        page.pop_dialog()

    async def synchronize(_):
        if not getattr(page,'_xopilot_can_sync',lambda:True)():
            status.value='Завершите ответ, звонок или редактирование и закройте защищённый чат';page.update();return
        manual.disabled=True;status.value='Синхронизируем выбранные данные…';page.update()
        try:
            result=await asyncio.to_thread(sync.run)
            if result.get('busy'):
                refresh();status.value+='\nСинхронизация уже выполняется';return
            callback=getattr(page,'_xopilot_sync_refresh',None)
            if callback:callback()
            refresh()
            if result.get('conflicts'):status.value+='\nЕсть разные версии. Они сохранены, выберите действие в конфликтах'
        except Exception as exc:status.value=str(exc)
        finally:manual.disabled=not enabled.value or not sync.key_ready();page.update()
    manual.on_click=synchronize

    def password_dialog(_=None, enable_after=False):
        password=modern_input(ft.TextField(label='Пароль синхронизации',password=True,can_reveal_password=True,autofocus=True))
        repeat=modern_input(ft.TextField(label='Повторный пароль',password=True,can_reveal_password=True))
        error=ft.Text('',size=12,color=color('#47747a'))
        submit=action_button('Продолжить');cancel=ft.TextButton(content='Отмена')
        async def unlock(_):
            submit.disabled=cancel.disabled=True;error.value='Подготавливаем ключ…';page.update()
            try:
                await asyncio.to_thread(sync.setup,password.value or '',repeat.value or '')
                if enable_after:
                    sync.save_options({'enabled':True})
                    enabled.value=True
                password.value=repeat.value='';page.pop_dialog();refresh()
                if enabled.value:page.run_task(synchronize,None)
            except Exception as exc:error.value=str(exc)
            finally:submit.disabled=cancel.disabled=False;page.update()
        submit.on_click=repeat.on_submit=unlock
        def cancel_setup(_):
            password.value=repeat.value=''
            page.pop_dialog()
        cancel.on_click=cancel_setup
        page.show_dialog(ft.AlertDialog(modal=True,bgcolor=color('#eafffa'),title=ft.Text('Пароль синхронизации'),
            content=ft.Column(width=380,height=260,spacing=12,scroll=ft.ScrollMode.AUTO,controls=[
                ft.Text('Это отдельный пароль, не пароль аккаунта. Он понадобится на новом устройстве. Без него облачные данные восстановить нельзя.',size=12),password,repeat,error]),actions=[cancel,submit]))
    setup.on_click=password_dialog
    def forget_key(_):
        sync.forget_key();enabled.value=auto.value=False;refresh();page.update()
    forget.on_click=forget_key
    conflicts.on_click=lambda _:open_conflicts(page,refresh)
    refresh()
    dialog=ft.AlertDialog(bgcolor=color('#eafffa'),title=ft.Text('Синхронизация'),on_dismiss=flush_limit,
        content=ft.Column(width=520,height=480,scroll=ft.ScrollMode.AUTO,spacing=10,controls=[
            enabled,auto,preset,*checks.values(),
            ft.Text('Временные чаты не отправляются. Защищённые чаты синхронизируются после закрытия и сохраняют собственный пароль.',size=11,color=color('#47747a')),
            ft.Divider(),setup,forget,traffic,limit,
            ft.Text('Считаются исходящие запросы синхронизации и облачного хранилища, включая повторы. Вход и управление аккаунтом, курсы валют, входящий трафик и расходы TLS/TCP не входят в лимит.',size=11,color=color('#47747a')),
            status,conflicts]),actions=[ft.TextButton(content='Закрыть',on_click=close),manual])
    dialog._xopilot_sync_safe=True
    page.show_dialog(dialog)
    async def monitor():
        previous=sync.status()
        while dialog.open:
            await asyncio.sleep(1)
            if not dialog.open:return
            current=sync.status()
            if current==previous:continue
            previous=current
            try:refresh()
            except ValueError:return  # Account was signed out on another page.
            page.update()
    page.run_task(monitor)


def open_conflicts(page,on_changed=lambda:None):
    content=ft.Column(width=470,height=330,scroll=ft.ScrollMode.AUTO,spacing=12)
    error=ft.Text('',size=12)
    generation=0
    pending=[]

    def version_card(label,data):
        avatar=(ft.Image(src=base64.b64decode(data['avatar']),width=44,height=44,border_radius=22)
                if data.get('avatar') else ft.Icon(ft.Icons.PERSON_OUTLINE,size=40))
        memory=data.get('memory',{'enabled':True,'automatic':True,'items':[]})
        facts=memory.get('items',[])
        details='Память: '+str(len(facts))+' записей · '+('включена' if memory.get('enabled',True) else 'выключена')
        details+=' · автосохранение '+('вкл.' if memory.get('automatic',True) else 'выкл.')
        return ft.Container(padding=10,border_radius=12,bgcolor=color('#f3fffc'),content=ft.Column(spacing=5,controls=[
            ft.Text(label,weight=ft.FontWeight.BOLD),
            ft.Row(controls=[avatar,ft.Text(data['name'],expand=True)]),ft.Text(details,size=11),
            *([ft.ExpansionTile(title=ft.Text('Посмотреть записи памяти',size=12),controls=[
                ft.ListView(height=160,spacing=8,build_controls_on_demand=True,controls=[ft.Text(f['text'],size=12) for f in facts])])]
              if facts else [])]))

    async def load_preview(identifier,panel,state,buttons,version):
        try:
            result=await asyncio.to_thread(sync.profile_conflict_preview,identifier)
            if not dialog.open or generation!=version:return
            state['expected']=result['expected']
            panel.controls=[version_card('На этом устройстве',result['local']),version_card('В облаке',result['cloud'])]
            for button in buttons:button.disabled=False
        except Exception as exc:
            if not dialog.open or generation!=version:return
            panel.controls=[ft.Text('Не удалось сравнить версии: '+str(exc),size=12)]
        page.update()

    def launch_previews():
        for args in pending:page.run_task(load_preview,*args)
        pending.clear()

    def render():
        nonlocal generation
        generation+=1;pending.clear()
        rows=[]
        for key,change in sync.conflict_items().items():
            async def keep(_,identifier=key):
                try:
                    await asyncio.to_thread(sync.resolve_keep_both,identifier);render();on_changed()
                except Exception as exc:error.value=str(exc)
                page.update()
            record=sync.read_ledger(sync.owner())['records'][key]
            preview=[]
            if record['scope'] in ('protected','profile'):
                state={}
                async def choose(_,identifier=key,scope=record['scope'],state=state,version='local'):
                    try:
                        for button in state['buttons']:button.disabled=True
                        page.update()
                        if scope=='profile':
                            if 'expected' not in state:raise ValueError('Дождитесь сравнения версий')
                            await asyncio.to_thread(sync.resolve_profile,identifier,version,expected=state['expected'])
                        else:await asyncio.to_thread(sync.resolve_private,identifier,version)
                        if not dialog.open:return
                        error.value='';render();launch_previews();on_changed()
                        if scope=='profile':
                            refresh=getattr(page,'_xopilot_profile_refresh',None)
                            if refresh:refresh()
                    except Exception as exc:
                        if not dialog.open:return
                        error.value=str(exc);render();launch_previews()
                    page.update()
                async def choose_local(e,handler=choose):await handler(e,version='local')
                async def choose_cloud(e,handler=choose):await handler(e,version='cloud')
                buttons=[action_button('Оставить на устройстве',secondary=True,on_click=choose_local),action_button('Принять из облака',secondary=True,on_click=choose_cloud)]
                state['buttons']=buttons
                if record['scope']=='profile':
                    panel=ft.Column(controls=[ft.Text('Сравниваем имя, фото и память…',size=12)])
                    preview=[panel]
                    for button in buttons:button.disabled=True
                    pending.append((key,panel,state,buttons,generation))
                note='Сравните имя, фото и память. Другая версия сохранится в зашифрованной базе для восстановления.' if record['scope']=='profile' else 'Сначала закройте защищённый чат. Другая версия останется зашифрованной копией в управлении хранилищем.'
            else:
                buttons=[ft.OutlinedButton(content='Сохранить обе версии',on_click=keep)]
                note='Локальные изменения сохранены. Можно оставить обе версии отдельными элементами.'
            rows.append(ft.Container(padding=12,border_radius=14,bgcolor=color('#dff8f3'),content=ft.Column(controls=[
                ft.Text('Разные версии: '+('профиль' if record['scope']=='profile' else 'защищённый чат' if record['scope']=='protected' else change['kind']),weight=ft.FontWeight.BOLD),
                ft.Text(note,size=12),*preview,*buttons])))
        content.controls=rows or [ft.Text('Конфликтов нет')]
    dialog=ft.AlertDialog(bgcolor=color('#eafffa'),title=ft.Text('Конфликты синхронизации'),
        content=ft.Column(width=470,height=370,controls=[content,error]),actions=[ft.TextButton(content='Закрыть',on_click=lambda _:page.pop_dialog())])
    render();page.show_dialog(dialog);launch_previews()
