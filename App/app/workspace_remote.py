"""
Файл: /App/app/workspace_remote.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Локальный/удалённый режим пространства, задания и подтверждения прямо в чате.
"""
import asyncio
import flet as ft
from .palette import color
from .remote_browser import approval_content,open_remote
try:
    from ..services import remote_tasks,cloud_sync
    from ..services.platforms import is_android
except ImportError:
    from services import remote_tasks,cloud_sync
    from services.platforms import is_android


class WorkspaceRemote:
    def __init__(self,page,get_chat,get_workspace,get_list,on_user,on_refresh,on_changed):
        self.page,self.get_chat,self.get_workspace=page,get_chat,get_workspace
        self.get_list,self.on_user,self.on_refresh,self.on_changed=get_list,on_user,on_refresh,on_changed
        self.busy=False;self.job=None
        self.local=ft.TextButton(content='Локально',icon=ft.Icons.SMARTPHONE_ROUNDED,on_click=self.local_mode)
        self.pc=ft.TextButton(content='На ПК',icon=ft.Icons.COMPUTER_ROUNDED,on_click=self.pc_mode)
        self.selector=ft.Container(visible=False,padding=ft.Padding.only(bottom=6),content=ft.Row(spacing=4,controls=[self.local,self.pc]))

    @property
    def eligible(self):return is_android() and self.get_workspace()!='all' and isinstance(self.get_chat(),int) and self.get_chat()>0
    @property
    def target(self):return remote_tasks.workspace_target(self.get_workspace()) if self.eligible else ''

    def refresh(self):
        self.selector.visible=self.eligible
        target=self.target
        self.local.disabled=self.pc.disabled=self.busy
        self.local.style=ft.ButtonStyle(bgcolor=color('#dff8f3') if not target else ft.Colors.TRANSPARENT)
        self.pc.style=ft.ButtonStyle(bgcolor=color('#dff8f3') if target else ft.Colors.TRANSPARENT)

    def local_mode(self,_):
        remote_tasks.workspace_target(self.get_workspace(),'');self.refresh();self.page.update()

    async def pc_mode(self,_):
        try:
            rows=await asyncio.to_thread(remote_tasks.hosts)
            def select(target):
                remote_tasks.workspace_target(self.get_workspace(),target);self.refresh();self.page.update()
            if len(rows)==1:select(rows[0]['session_id']);return
            if not rows:open_remote(self.page);return
            def choose(target):select(target);self.page.pop_dialog()
            self.page.show_dialog(ft.AlertDialog(title=ft.Text('На каком компьютере работать?'),
                content=ft.Column(tight=True,controls=[ft.ListTile(leading=ft.Icon(ft.Icons.COMPUTER),title=ft.Text(row['name']),
                    subtitle=ft.Text('В сети' if row['online'] else 'Не в сети'),on_click=lambda _,target=row['session_id']:choose(target)) for row in rows]),
                actions=[ft.TextButton(content='Отмена',on_click=lambda _:self.page.pop_dialog())]))
        except Exception as exc:self.page.show_dialog(ft.SnackBar(ft.Text(str(exc))))

    async def stop(self):
        if self.job:await asyncio.to_thread(remote_tasks.cancel,self.job)

    async def send(self,text,attachments):
        if self.busy:raise ValueError('Дождитесь завершения задания на ПК')
        target=self.target
        if not target:raise ValueError('Выберите связанный ПК')
        cid=self.get_chat();workspace=self.get_workspace()
        self.busy=True;self.refresh();self.on_changed()
        status=ft.Text('Отправляю на компьютер…',size=12,color=color('#47747a'))
        details=ft.Column(spacing=8)
        card=ft.Container(padding=12,border_radius=16,bgcolor=color('#f3fffc'),content=ft.Column(spacing=8,
            controls=[ft.Row(controls=[ft.Icon(ft.Icons.COMPUTER_ROUNDED,size=18,color=color('#087f8c')),status]),details]))
        def update():
            if self.get_chat()==cid:self.page.update()
        try:
            await self.on_user(text,attachments)
            self.get_list().controls.insert(0,card);self.page.update()
            self.job=await asyncio.to_thread(remote_tasks.submit,target,text,workspace,chat_id=cid)
            question=None
            while getattr(self.page,'_xopilot_connected',True):
                try:row=await asyncio.to_thread(remote_tasks.inspect,self.job)
                except Exception:
                    status.value='Нет связи · задание остаётся на ПК';update();await asyncio.sleep(3);continue
                value=row.get('decoded_result') or {}
                labels={'queued':'Ожидаем компьютер…','running':'ИИ работает на ПК','approval':'Нужно ваше разрешение',
                    'completed':'Готово','failed':'Не удалось выполнить','cancelled':'Задание отменено','expired':'Время задания истекло'}
                status.value=labels.get(row['state'],row['state'])
                if row['state']=='approval' and row.get('question')!=question:
                    question=row['question'];request=value['request'];title,preview=approval_content(request)
                    async def decide(approved,q=question,r=request):
                        try:
                            await asyncio.to_thread(remote_tasks.decide,self.job,q,r,approved)
                            details.controls=[];status.value='Решение отправлено';update()
                        except Exception as exc:status.value=str(exc);update()
                    details.controls=[ft.Text(title,weight=ft.FontWeight.W_600),ft.Text(preview,size=12,font_family='monospace',selectable=True),
                        ft.Row(wrap=True,controls=[ft.TextButton(content='Отклонить',on_click=lambda _:self.page.run_task(decide,False)),
                            ft.FilledTonalButton(content='Подтвердить',on_click=lambda _:self.page.run_task(decide,True))])]
                elif row['state']!='approval':details.controls=[]
                if row['state'] in {'completed','failed','cancelled','expired'}:
                    if value.get('error'):details.controls=[ft.Text(value['error'],color=color('#c94b4b'))]
                    if row['state']=='completed':
                        await asyncio.to_thread(cloud_sync.run)
                        self.busy=False
                        self.on_refresh()
                    update();return row['state']=='completed'
                if value.get('progress') and row['state']=='running':status.value=value['progress']
                update();await asyncio.sleep(2)
        except remote_tasks.DeliveryPending as exc:
            self.job=exc.identifier;status.value='Доставка пока не подтверждена';update()
            async def retry(_):
                try:await asyncio.to_thread(remote_tasks.retry,self.job);status.value='Доставлено · результат придёт через синхронизацию'
                except Exception as error:status.value=str(error)
                update()
            details.controls=[ft.TextButton(content='Проверить доставку',on_click=retry)]
        except Exception as exc:status.value=str(exc);update()
        finally:
            self.busy=False;self.refresh();self.on_changed()
