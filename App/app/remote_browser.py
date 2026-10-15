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
    closed=False
    devices=ft.Column(spacing=10)
    status=ft.Text('Ищем ваши устройства…',size=12,color=color('#47747a'))
    async def refresh():
        while not closed:
            try:
                rows=await asyncio.to_thread(remote_tasks.devices)
                controls=[]
                for item in rows:
                    async def connect(_,target=item['session_id']):
                        try:
                            await asyncio.to_thread(remote_tasks.request_pair,target)
                            status.value='Запрос отправлен. Подтвердите привязку на компьютере.'
                        except Exception as exc:status.value=str(exc)
                        page.update()
                    async def disconnect(_,target=item['session_id']):
                        try:
                            await asyncio.to_thread(remote_tasks.unlink,target)
                            status.value='Устройства отвязаны'
                        except Exception as exc:status.value=str(exc)
                        page.update()
                    action=ft.TextButton(content='Отвязать',on_click=disconnect) if item['linked'] else ft.FilledTonalButton(
                        content='Ожидание' if item['pending'] else 'Связать',disabled=item['pending'],on_click=connect)
                    controls.append(ft.Container(padding=14,border_radius=20,bgcolor=color('#f3fffc'),content=ft.Row(
                        controls=[ft.Icon(ft.Icons.COMPUTER_ROUNDED,color=color('#087f8c')),
                            ft.Column(expand=True,spacing=4,controls=[ft.Text(item['name'],weight=ft.FontWeight.W_600),
                                ft.Text(('Связано · ' if item['linked'] else '')+('В сети' if item['online'] else 'Не в сети'),size=11,color=color('#47747a'))]),action])))
                devices.controls=controls or [ft.Text('Откройте Xopilot на ПК и войдите в этот же аккаунт. Компьютер появится здесь.',color=color('#47747a'))]
                if rows:status.value='После привязки выберите «На ПК» в строке ввода рабочего пространства.'
                page.update()
            except Exception as exc:status.value=str(exc);page.update()
            await asyncio.sleep(5)
    def close(_):
        nonlocal closed
        closed=True;page.pop_dialog()
    def dismiss(_):
        nonlocal closed
        closed=True
    page.show_dialog(ft.AlertDialog(title=ft.Text('Мои компьютеры'),bgcolor=color('#eafffa'),
        shape=ft.RoundedRectangleBorder(radius=24),content=ft.Column(width=580,height=min(500,max(260,(page.height or 800)-230)),
            scroll=ft.ScrollMode.AUTO,spacing=16,controls=[ft.Text('Свяжите телефон с вашим ПК. Запрос нужно подтвердить на компьютере.',size=13,color=color('#47747a')),devices,status]),
        actions=[ft.FilledTonalButton(content='Готово',on_click=close)],on_dismiss=dismiss))
    page.run_task(refresh)


async def listen_for_pairing(page):
    if is_android():return
    shown=set();active=False
    guard=lambda:getattr(page,'_xopilot_can_sync',lambda:False)() and getattr(page,'_xopilot_can_release_model',lambda:False)()
    while getattr(page,'_xopilot_connected',True):
        try:
            await asyncio.to_thread(remote_tasks.announce)
            await asyncio.to_thread(remote_tasks.start,guard=guard)
            requests=await asyncio.to_thread(remote_tasks.pairing_requests)
            if active:
                await asyncio.sleep(5);continue
            for request in requests:
                sender=request['sender']
                if sender in shown:continue
                shown.add(sender);active=True
                message=ft.Text('Разрешение действует до отвязки устройства. Команды и изменения файлов потребуют отдельного подтверждения.',size=13)
                buttons=ft.Row(alignment=ft.MainAxisAlignment.END)
                async def decide(approved,peer=sender):
                    nonlocal active
                    buttons.disabled=True;page.update()
                    try:
                        await asyncio.to_thread(remote_tasks.confirm_pair,peer,approved,guard=guard)
                        active=False;shown.discard(peer);page.pop_dialog()
                    except Exception as exc:message.value=str(exc);buttons.disabled=False;page.update()
                buttons.controls=[ft.TextButton(content='Отклонить',on_click=lambda _:page.run_task(decide,False)),
                    ft.FilledButton(content='Связать устройства',on_click=lambda _:page.run_task(decide,True))]
                page.show_dialog(ft.AlertDialog(modal=True,title=ft.Text(request['name']+' хочет связаться с этим ПК'),
                    bgcolor=color('#eafffa'),content=ft.Column(width=430,tight=True,spacing=18,
                        controls=[ft.Icon(ft.Icons.PHONELINK_ROUNDED,size=38,color=color('#087f8c')),message,buttons])))
                break
        except Exception:pass  # Local mode remains available without cloud credentials/network.
        await asyncio.sleep(5)
