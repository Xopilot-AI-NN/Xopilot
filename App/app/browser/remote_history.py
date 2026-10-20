"""
Файл: /App/app/browser/remote_history.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: История зашифрованных заданий с расшифровкой только на устройстве владельца.
"""
import asyncio
from datetime import datetime
import flet as ft
from ..theme.palette import color
try:
    from ...services import remote_tasks
except ImportError:
    from services import remote_tasks


def open_history(page):
    rows=ft.Column(spacing=10)
    status=ft.Text('Загружаем историю…',size=12,color=color('#47747a'))
    offset=0;closed=False
    more=ft.TextButton(content='Показать ещё',visible=False)
    async def load(_=None):
        nonlocal offset
        more.disabled=True
        try:
            result=await asyncio.to_thread(remote_tasks.history,offset)
            if closed:return
            status.value=f"Завершённые задания за {result['history_days']} дн. · содержимое расшифровано на этом устройстве"
            for item in result['jobs']:
                title=item['task'].get('prompt','Задание')
                reply=item['result'].get('reply','') if isinstance(item.get('result'),dict) else ''
                state={'completed':'Выполнено','failed':'Ошибка','cancelled':'Отменено'}[item['state']]
                stamp=datetime.fromtimestamp(item['updated_at']).strftime('%d.%m.%Y · %H:%M')
                rows.controls.append(ft.Container(padding=14,border_radius=20,bgcolor=color('#f3fffc'),content=ft.Column(spacing=8,controls=[
                    ft.Text(title,max_lines=3,overflow=ft.TextOverflow.ELLIPSIS,weight=ft.FontWeight.W_600),
                    ft.Text(state+' · '+stamp,size=11,color=color('#47747a')),
                    *([ft.ExpansionTile(title=ft.Text('Результат',size=12),controls=[ft.Text(reply,selectable=True)])] if reply else [])])))
            if not rows.controls:rows.controls=[ft.Text('Завершённых заданий пока нет.')]
            offset=result['next_offset'];more.visible=result['has_more']
        except Exception as exc:
            if closed:return
            status.value=('История заданий доступна в Elite, Ultra и Led. Подписку можно получить у администратора.'
                          if getattr(exc,'code',None)=='subscription_required' or 'subscription_required' in str(exc) else str(exc))
        more.disabled=False
        if not closed:page.update()
    more.on_click=load
    def close(_):
        nonlocal closed
        closed=True;page.pop_dialog()
    def dismiss(_):
        nonlocal closed
        closed=True
    page.show_dialog(ft.AlertDialog(title=ft.Text('История заданий'),bgcolor=color('#eafffa'),
        shape=ft.RoundedRectangleBorder(radius=24),content=ft.Column(width=580,height=min(530,max(230,(page.height or 800)-240)),
            scroll=ft.ScrollMode.AUTO,spacing=14,controls=[status,rows,more]),
        actions=[ft.FilledTonalButton(content='Готово',on_click=close)],on_dismiss=dismiss))
    page.run_task(load)
