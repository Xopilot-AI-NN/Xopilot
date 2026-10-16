"""
Файл: /App/app/tasks/task_browser.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Текущие команды, вывод процессов и управление задачей ИИ.
"""
import asyncio
import shlex
import flet as ft
from ..theme.palette import color, apply_palette
try:
    from ...services import task_processes
except ImportError:
    from services import task_processes


def open_tasks(page, task, *, active=lambda: False):
    rows=ft.Column(spacing=12)
    status=ft.Text(task.state if active() else 'Задача ИИ завершена',size=13)
    error=ft.Text('',size=12,color=color('#c94b4b'))
    pause=ft.FilledButton(content='Продолжить' if task.paused else 'Пауза')
    def toggle(_):
        task.resume() if task.paused else task.pause()
        pause.content='Продолжить' if task.paused else 'Пауза';page.update()
    pause.on_click=toggle
    async def stop(_,identifier):
        try:
            # UI belongs to the local app owner; explicit button stops this id.
            await asyncio.to_thread(task_processes.stop_process,identifier)
        except Exception as exc:error.value=str(exc)
        page.update()
    async def refresh():
        while dialog.open:
            status.value=task.state if active() else 'Задача ИИ завершена · фоновые процессы доступны ниже'
            pause.visible=active();pause.content='Продолжить' if task.paused else 'Пауза'
            controls=[]
            for item in task_processes.snapshots():
                controls.append(ft.Container(padding=14,border_radius=16,bgcolor=color('#f3fffc'),
                    content=ft.Column(spacing=8,controls=[ft.Row(controls=[
                        ft.Icon(ft.Icons.TERMINAL,color=color('#087f8c')),
                        ft.Text(shlex.join(item['argv']),expand=True,selectable=True,font_family='monospace',size=12),
                        ft.IconButton(icon=ft.Icons.STOP_CIRCLE_OUTLINED,tooltip='Остановить процесс',visible=item['running'],
                            on_click=lambda e,identifier=item['id']:page.run_task(stop,e,identifier))]),
                        ft.Text(f"PID {item['pid']} · "+('Выполняется' if item['running'] else f"Завершён · код {item['exit_code']}"),size=11),
                        ft.Text(item['cwd'],size=11,color=color('#47747a')),
                        ft.Text(item['output'][-24000:] or 'Вывод ещё не поступил',font_family='monospace',size=11,selectable=True)])))
            rows.controls=controls or [ft.Text('Системные команды ещё не запускались',size=13)]
            apply_palette(rows);page.update()
            await asyncio.sleep(1)
    width=page.width if isinstance(page.width,(int,float)) else 1000
    height=page.height if isinstance(page.height,(int,float)) else 800
    dialog=ft.AlertDialog(bgcolor=color('#eafffa'),shape=ft.RoundedRectangleBorder(radius=22),
        title=ft.Text('Задача и команды'),
        content=ft.Column(width=min(750,max(240,width-72)),
            height=min(560,max(300,height-200)),controls=[status,pause,error,ft.ListView(expand=True,controls=[rows])]),
        actions=[ft.TextButton(content='Закрыть',on_click=lambda _:page.pop_dialog())])
    apply_palette(dialog);page.show_dialog(dialog);page.run_task(refresh)
