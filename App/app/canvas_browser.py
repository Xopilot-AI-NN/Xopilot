"""
Файл: /App/app/canvas_browser.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Компактный браузер Canvas в стиле Material 3 с навигацией и живой страницей.
"""
import asyncio
from pathlib import Path
import flet as ft
from .palette import color


def browser_theme(title):
    return {'title': title, 'surface': color('#eafffa'), 'raised': color('#f3fffc'),
            'text': color('#123b43'), 'muted': color('#47747a'), 'accent': color('#087f8c')}


def show_browser(page, service, chat_id, workspace_id, identifier, frame, title):
    size = [960, 600]
    pixels = [frame.get('width', 960), frame.get('height', 600)]
    state = {'closed': False, 'resize': None}
    lock = asyncio.Lock()
    image = ft.Image(src=Path(frame['screenshot']).read_bytes(), fit=ft.BoxFit.FILL,
                     gapless_playback=True, expand=True, semantics_label='Страница сайта Canvas')
    address = ft.Text('canvas / '+title, size=13, color=color('#123b43'),
                      max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True)
    caption = ft.Text(title, size=13, weight=ft.FontWeight.W_600, color=color('#123b43'),
                      max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True)
    feedback = ft.Text('Локальный сайт · Canvas', size=11, color=color('#47747a'), expand=True)
    progress = ft.ProgressBar(height=2, color=color('#087f8c'), opacity=0)

    async def act(action):
        async with lock:
            if state['closed']: return
            progress.opacity=1;page.update()
            try:
                result=await asyncio.to_thread(service.inspect,chat_id,workspace_id,identifier,action)
                if state['closed']: return
                image.src=Path(result['screenshot']).read_bytes()
                pixels[:]=[result.get('width',960),result.get('height',600)]
                caption.value=result.get('title') or title
                address.value='canvas / '+title+result.get('fragment','')
                back.disabled=not result.get('can_go_back',False)
                forward.disabled=not result.get('can_go_forward',False)
                feedback.value='Локальный сайт · Canvas'
            except Exception as exc: feedback.value='Не удалось выполнить действие: '+str(exc)
            finally:
                progress.opacity=0
                if not state['closed']:page.update()

    def action(value):
        return lambda _: page.run_task(act, value)

    def button(icon, label, handler, **kwargs):
        return ft.IconButton(icon=icon, tooltip=label, on_click=handler, icon_size=20,
                             icon_color=color('#123b43'), **kwargs)

    back=button(ft.Icons.ARROW_BACK_ROUNDED,'Назад',action({'action':'back'}),disabled=not frame.get('can_go_back'))
    forward=button(ft.Icons.ARROW_FORWARD_ROUNDED,'Вперёд',action({'action':'forward'}),disabled=not frame.get('can_go_forward'))

    def clicked(event):
        p=event.local_position
        page.run_task(act,{'action':'point','x':p.x*pixels[0]/max(1,size[0]),
                           'y':p.y*pixels[1]/max(1,size[1])})

    def resized(event):
        measured=[max(1,round(event.width)),max(1,round(event.height))]
        if measured==size or state['closed']:return
        size[:]=measured
        image.width,image.height=size
        if state['resize']:state['resize'].cancel()
        async def update_viewport():
            await asyncio.sleep(.15)
            state['resize']=None
            await act({'action':'viewport','width':round(size[0]),'height':round(size[1])})
        state['resize']=page.run_task(update_viewport)

    typed=ft.TextField(hint_text='Текст для выбранного поля сайта',dense=True,expand=True,
                       border=ft.InputBorder.NONE,content_padding=8,text_size=13)
    def enter(_):
        if typed.value:
            value=typed.value;typed.value='';page.run_task(act,{'action':'type','text':value})
    typed.on_submit=enter

    async def close(_):
        state['closed']=True
        if state['resize']:state['resize'].cancel()
        page.pop_dialog()
        await asyncio.to_thread(service.close,chat_id,identifier)

    async def dismissed(_):
        state['closed']=True
        if state['resize']:state['resize'].cancel()
        await asyncio.to_thread(service.close,chat_id,identifier)

    toolbar=ft.Container(padding=ft.Padding.symmetric(horizontal=12,vertical=6),
        content=ft.Column(spacing=2,controls=[
            ft.Row(controls=[ft.Icon(ft.Icons.LANGUAGE_ROUNDED,size=18,color=color('#087f8c')),caption,
                button(ft.Icons.CLOSE_ROUNDED,'Закрыть браузер',close)]),
            ft.Row(spacing=2,controls=[back,forward,
                button(ft.Icons.REFRESH_ROUNDED,'Обновить страницу',action({'action':'reload'})),
                ft.Container(expand=True,bgcolor=color('#f3fffc'),border_radius=24,padding=12,
                    tooltip='Локальный сайт Canvas',content=ft.Row(spacing=8,controls=[
                        ft.Icon(ft.Icons.SHIELD_OUTLINED,size=16,color=color('#087f8c')),address]))])]))
    surface=ft.Container(expand=True,bgcolor='#ffffff',clip_behavior=ft.ClipBehavior.HARD_EDGE,
        on_size_change=resized,content=ft.GestureDetector(expand=True,content=image,on_tap_up=clicked))
    footer=ft.Container(padding=ft.Padding.symmetric(horizontal=12,vertical=4),
        content=ft.Row(spacing=2,controls=[typed,button(ft.Icons.KEYBOARD_RETURN_ROUNDED,'Ввести текст',enter),
            button(ft.Icons.KEYBOARD_ARROW_UP_ROUNDED,'Прокрутить вверх',action({'action':'scroll','dy':-400})),
            button(ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED,'Прокрутить вниз',action({'action':'scroll','dy':400}))]))
    dialog=ft.AlertDialog(modal=True,bgcolor=color('#eafffa'),
        inset_padding=12,content_padding=0,shape=ft.RoundedRectangleBorder(radius=24),
        content=ft.Container(width=min(1200,max(240,(page.width or 1000)-48)),
            height=max(260,(page.height or 800)-64),clip_behavior=ft.ClipBehavior.HARD_EDGE,border_radius=24,
            content=ft.Column(spacing=0,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,controls=[toolbar,progress,surface,footer,
                ft.Container(padding=ft.Padding.only(left=16,right=16,bottom=10),content=feedback)])),
        on_dismiss=dismissed)
    page.show_dialog(dialog)
    return dialog
