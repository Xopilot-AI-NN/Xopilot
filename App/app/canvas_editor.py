"""
Файл: /App/app/canvas_editor.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Редактор текста, кода, рисунков и интерактивных сайтов с экспортом Office.
"""
"""A real persisted editor with freehand drawing and attachment/export actions."""
import asyncio
import os
from pathlib import Path
import flet as ft
import flet.canvas as cv
from .palette import color, apply_palette
try:
    from ..services import canvases
    from ..services.material_store import store_material
    from ..services.platforms import is_android,compact_layout,available_height
except ImportError:
    from services import canvases
    from services.material_store import store_material
    from services.platforms import is_android,compact_layout,available_height


def build_canvas_dialog(page, chat_id, workspace_id='all', on_attach=None, *, document_store=None, material_store=None, storage_label='Сохранено на устройстве'):
    canvases = document_store or globals()['canvases']
    store_material = material_store or globals()['store_material']
    width = min(850, max(220, (page.width or 1000) - 112))
    height = min(620, max(320, (page.height or 760) - 180))
    documents = canvases.list_documents(chat_id, workspace_id)
    current = dict(documents[-1]) if documents else canvases.create_document(chat_id=chat_id, workspace_id=workspace_id)
    status = ft.Text(storage_label, size=11, color=color('#47747a'))
    title = ft.TextField(label='Название', value=current['title'])
    compact = compact_layout(page.width)
    editor = ft.TextField(value=current.get('content', ''), multiline=True, min_lines=5 if compact else 9, max_lines=12 if compact else 20,
                         hint_text='Пишите текст или код…', text_style=ft.TextStyle(font_family='monospace'))
    kinds = {'text': 'Текст', 'code': 'Код', 'drawing': 'Рисунок', 'web': 'Сайт · HTML/CSS/JS'}
    if chat_id < 0: kinds.pop('web')
    mode = ft.Dropdown(label='Тип Canvas', value=current['kind'], width=180,
                       options=[ft.DropdownOption(key=k, text=v) for k, v in kinds.items()])
    selection = ft.Dropdown(label='Документ', expand=True)
    picker = ft.FilePicker()
    export_format = ft.Dropdown(label='Формат экспорта', value='original', width=180,
        options=[ft.DropdownOption(key='original', text='Исходный файл'),
                 *[ft.DropdownOption(key=k, text=k.upper()) for k in ('docx','pdf','xlsx','csv','txt')]])
    dimensions = [width - 28, 300]
    paint_color = '#123b43'
    brush_width = 3
    active_stroke = None
    drawing_open = False
    pending_save=None
    drawing = cv.Canvas(width=width-2, height=300, expand=False)
    drawing.__dict__['_xopilot_fixed_colors'] = True

    def persist(_=None):
        nonlocal current,pending_save
        if pending_save:pending_save.cancel();pending_save=None
        current.update(title=(title.value or '').strip(), content=editor.value or '', kind=mode.value)
        if mode.value == 'drawing':
            current['drawing_size'] = list(dimensions)
        try:
            current = canvases.save_document(current)
            fill_selection()
            status.value = storage_label
            return True
        except Exception as exc:
            status.value = f'Не удалось сохранить: {exc}'
            return False

    async def changed(_):
        nonlocal pending_save
        if pending_save:pending_save.cancel()
        async def save_later():
            nonlocal pending_save
            await asyncio.sleep(0.4);pending_save=None
            persist();status.update();selection.update()
        pending_save=page.run_task(save_later)

    title.on_change = changed
    editor.on_change = changed

    def render_drawing(update=True):
        w, h = dimensions
        drawing.shapes = [cv.Circle(points[0][0]*w,points[0][1]*h,stroke['width']/2,
                                   paint=ft.Paint(color=stroke['color'])) if len(points)==1 else cv.Path(elements=[cv.Path.MoveTo(points[0][0]*w, points[0][1]*h),
                                *[cv.Path.LineTo(x*w, y*h) for x, y in points[1:]]],
                       paint=ft.Paint(color=stroke['color'], stroke_width=stroke['width'],
                                      style=ft.PaintingStyle.STROKE, stroke_cap=ft.StrokeCap.ROUND))
            for stroke in current.get('strokes', []) if (points := stroke['points'])]
        if update and drawing_open:
            drawing.update()

    def resized(e):
        dimensions[:] = [max(1, e.width), max(1, e.height)]
        render_drawing()
    drawing.on_resize = resized

    def point(e):
        p = e.local_position
        return [max(0, min(1, p.x/dimensions[0])), max(0, min(1, p.y/dimensions[1]))]

    def start_stroke(e):
        nonlocal active_stroke
        if active_stroke is not None:return
        active_stroke = {'color': paint_color, 'width': brush_width, 'points': [point(e)]}
        current.setdefault('strokes', []).append(active_stroke)
        render_drawing()

    def move_stroke(e):
        if active_stroke is not None:
            next_point=point(e)
            if next_point==active_stroke['points'][-1]:return
            active_stroke['points'].append(next_point)
            render_drawing()

    def finish_stroke(_):
        nonlocal active_stroke
        active_stroke = None
        persist()
        page.update()

    def undo(_):
        if current.get('strokes'):
            current['strokes'].pop()
            persist()
            render_drawing()
            page.update()

    def choose_ink(value):
        nonlocal paint_color
        paint_color = value
        status.value = 'Цвет кисти выбран'
        page.update()

    def change_width(e):
        nonlocal brush_width
        brush_width = e.control.value
    brush = ft.Row(wrap=True, spacing=4, controls=[
        *[ft.IconButton(icon=ft.Icons.CIRCLE, icon_color=ink, tooltip=f'Кисть {ink}',
                       on_click=lambda _, value=ink: choose_ink(value))
          for ink in ('#123b43', '#7657ff', '#0083e8', '#c94b4b', '#08734d')],
        ft.Slider(value=3, min=1, max=15, width=110, on_change=change_width),
        ft.IconButton(icon=ft.Icons.UNDO, tooltip='Отменить штрих', on_click=undo)])
    brush.__dict__['_xopilot_fixed_colors'] = True
    async def open_drawing(_):
        nonlocal drawing_open
        if is_android() and not page.web:
            try:
                try:from ..services.mobile_runtime import call_async
                except ImportError:from services.mobile_runtime import call_async
                await call_async('hideKeyboard');await asyncio.sleep(0.15)
            except Exception:pass
        drawing_open=True
        viewport=available_height(page) or 840
        drawing.width=max(180,min(800,(page.width or 1000)-80))
        drawing.height=max(100,min(450,viewport-300))
        drawing.expand=False
        dimensions[:]=[max(1,width-32),drawing.height]
        render_drawing(False)
        def close_drawing(_):
            nonlocal drawing_open
            finish_stroke(None)
            drawing_open=False
            page.pop_dialog()
        def dismiss_drawing(_):
            nonlocal drawing_open
            finish_stroke(None);drawing_open=False
        # The drawing surface has no scrolling ancestor. Otherwise a vertical
        # ListView wins Flutter's gesture arena and consumes drawing gestures.
        page.show_dialog(ft.AlertDialog(modal=True,bgcolor=color('#eafffa'),title=ft.Text('Рисование'),
            content=ft.Column(width=max(220,min(800,(page.width or 1000)-64)),
                height=max(180,min(600,viewport-180)),spacing=10,
                controls=[brush,ft.Container(height=drawing.height,bgcolor=ft.Colors.WHITE,
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,border_radius=12,
                    content=ft.GestureDetector(content=drawing,drag_interval=32,
                        on_tap_down=start_stroke,on_tap_up=finish_stroke,on_pan_start=start_stroke,
                        on_pan_update=move_stroke,on_pan_end=finish_stroke,on_pan_cancel=finish_stroke))]),
            actions=[ft.TextButton(content='Готово',on_click=close_drawing)],on_dismiss=dismiss_drawing))
    draw_area = ft.Column(visible=current['kind']=='drawing',controls=[
        ft.FilledButton(content='Рисовать',icon=ft.Icons.BRUSH,on_click=open_drawing),
        ft.Text('Полотно открывается отдельно: рисуйте пальцем или мышью, штрихи сохраняются автоматически.',size=12,color=color('#47747a'))])

    async def preview(_):
        if not persist(): page.update(); return
        if chat_id < 0:
            status.value='Просмотр сайта недоступен в защищённом чате';page.update();return
        try: from ..services import canvas_web
        except ImportError: from services import canvas_web
        identifier = current['id']
        try:
            from .canvas_browser import browser_theme, show_browser
            frame = await asyncio.to_thread(canvas_web.inspect,chat_id,workspace_id,identifier,
                                            presentation=browser_theme(current['title']))
            if is_android() and not page.web: return  # Native interactive WebView is already visible.
        except Exception as exc:
            status.value='Не удалось открыть сайт: '+str(exc);page.update();return
        show_browser(page,canvas_web,chat_id,workspace_id,identifier,frame,current['title'])

    web_area=ft.Column(visible=current['kind']=='web',controls=[
        ft.FilledButton(content='Открыть сайт',icon=ft.Icons.WEB,on_click=preview),
        ft.Text('Пишите HTML со встроенными CSS/JavaScript. ИИ может проверить DOM и нажимать элементы сайта. '
                'Внешние запросы, CDN и доступ к системе отключены.',size=12,color=color('#47747a'))])

    def fill_selection():
        selection.options = [ft.DropdownOption(key=item['id'], text=item['title'])
                             for item in canvases.list_documents(chat_id, workspace_id)]
        selection.value = current['id']

    def change_mode(_):
        editor.visible = mode.value != 'drawing'
        draw_area.visible = mode.value == 'drawing'
        web_area.visible = mode.value == 'web'
        export_format.visible = mode.value != 'drawing'
        persist()
        page.update()
    mode.on_select = change_mode

    def select_document(_):
        nonlocal current
        requested = selection.value
        if not persist():
            selection.value = current['id']
            page.update()
            return
        current = canvases.get_document(requested)
        title.value = current['title']
        editor.value = current.get('content', '')
        mode.value = current['kind']
        render_drawing(False)
        change_mode(None)

    selection.on_select = select_document

    def new_document(_):
        nonlocal current
        if not persist():
            page.update()
            return
        current = canvases.create_document(chat_id=chat_id, workspace_id=workspace_id)
        title.value, editor.value, mode.value = current['title'], '', 'text'
        fill_selection()
        change_mode(None)

    def delete_document(_):
        def remove(_):
            nonlocal current,pending_save
            try:
                if pending_save:pending_save.cancel();pending_save=None
                canvases.delete_document(current['id'])
                available=canvases.list_documents(chat_id,workspace_id)
                if not available:
                    page.pop_dialog()  # Confirmation.
                    page.pop_dialog()  # Editor; deleting the last document must leave it deleted.
                    page.update()
                    return
                current=dict(available[-1])
                title.value,editor.value,mode.value=current['title'],current.get('content',''),current['kind']
                fill_selection();render_drawing(False);change_mode(None);page.pop_dialog()
            except Exception as exc:status.value=str(exc)
            page.update()
        page.show_dialog(ft.AlertDialog(modal=True,title=ft.Text('Удалить Canvas?'),content=ft.Text(current['title']),
            actions=[ft.TextButton(content='Отмена',on_click=lambda _:page.pop_dialog()),ft.FilledButton(content='Удалить',on_click=remove)]))

    async def install_web(_):
        status.value='Скачиваю компонент просмотра сайтов…';page.update()
        try:
            try:from ..services.canvas_web import install_browser
            except ImportError:from services.canvas_web import install_browser
            await asyncio.to_thread(install_browser)
            status.value='Просмотр сайтов установлен. Откройте предпросмотр.'
        except Exception as exc:status.value='Не удалось установить просмотр: '+str(exc)
        page.update()

    def rendered_document():
        if export_format.value == 'original' or current['kind']=='drawing':
            return canvases.export_document(current)
        try: from ..services.office_documents import render
        except ImportError: from services.office_documents import render
        name=Path(current['title']).stem+'.'+export_format.value
        return render(name,current.get('content',''))

    async def export(_):
        if not persist():
            page.update()
            return
        try:
            name, data = await asyncio.to_thread(rendered_document)
            if is_android() and not page.web:
                try:
                    from ..services.mobile_documents import save_document
                except ImportError:
                    from services.mobile_documents import save_document
                status.value = 'Файл сохранён' if await save_document(name, data) else 'Сохранение отменено'
                page.update()
                return
            path = await picker.save_file(file_name=name, src_bytes=data)
            if path and not page.web:
                if not is_android():
                    await asyncio.to_thread(Path(path).write_bytes, data)
                status.value = 'Файл сохранён'
            else:
                status.value = 'Проверьте загрузки браузера' if page.web else 'Сохранение отменено'
        except Exception as exc:
            status.value = str(exc)
        page.update()

    async def attach(_):
        if not persist():
            page.update()
            return
        try:
            name, data = await asyncio.to_thread(rendered_document)
            path = await asyncio.to_thread(store_material, name, data=data)
            on_attach(path)
            status.value = 'Canvas добавлен во вложения черновика'
        except Exception as exc:
            status.value = str(exc)
        page.update()

    async def local_export(_):
        if not persist():
            page.update()
            return
        try:
            try:
                from ..services.exports import save_local_export
            except ImportError:
                from services.exports import save_local_export
            name, data = await asyncio.to_thread(rendered_document)
            path = await asyncio.to_thread(save_local_export, name, data)
            status.value = f'Локальная копия: {path}'
        except Exception as exc:
            status.value = f'Не удалось сохранить копию: {exc}'
        page.update()

    def close(_):
        if persist():
            page.pop_dialog()
        else:
            page.update()
    fill_selection()
    render_drawing(False)
    editor.visible = current['kind'] != 'drawing'
    return ft.AlertDialog(modal=True, bgcolor=color('#eafffa'), shape=ft.RoundedRectangleBorder(radius=22),
        title=ft.Row(controls=[ft.Icon(ft.Icons.DRAW_OUTLINED, color=color('#087f8c')),
                              ft.Text('Canvas', color=color('#123b43'), expand=True),
                              ft.IconButton(icon=ft.Icons.CLOSE, on_click=close, tooltip='Сохранить и закрыть')]),
        content=ft.Column(width=width, height=height, scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH, spacing=14,
            controls=[ft.Row(controls=[selection, ft.IconButton(icon=ft.Icons.ADD, tooltip='Новый Canvas', on_click=new_document),
                       ft.IconButton(icon=ft.Icons.DELETE_OUTLINE,tooltip='Удалить Canvas',on_click=delete_document)]),
                      title, ft.Row(wrap=True,controls=[mode,export_format]), editor, draw_area, web_area, status]),
        actions=[*([ft.TextButton(content='Сохранить', icon=ft.Icons.SAVE_OUTLINED, on_click=changed)] if not compact else []),
                 ft.TextButton(content='Экспорт', icon=ft.Icons.DOWNLOAD, on_click=export),
                 *([] if is_android() else [ft.TextButton(content='Установить просмотр сайтов',icon=ft.Icons.WEB,on_click=install_web)]),
                 *([ft.TextButton(content='Локальная копия', icon=ft.Icons.SAVE_ALT, on_click=local_export)]
                   if not is_android() and (not page.web or os.environ.get('XOPILOT_LOCAL_WEB') == '1') else []),
                 *([ft.FilledButton(content='В чат', icon=ft.Icons.ATTACH_FILE, on_click=attach)] if on_attach else [])])
