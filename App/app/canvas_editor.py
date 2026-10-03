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
except ImportError:
    from services import canvases
    from services.material_store import store_material


def build_canvas_dialog(page, chat_id, workspace_id='all', on_attach=None, *, document_store=None, material_store=None, storage_label='Сохранено на устройстве'):
    canvases = document_store or globals()['canvases']
    store_material = material_store or globals()['store_material']
    width = min(850, max(220, (page.width or 1000) - 112))
    height = min(620, max(320, (page.height or 760) - 180))
    documents = canvases.list_documents(chat_id, workspace_id)
    current = dict(documents[-1]) if documents else canvases.create_document(chat_id=chat_id, workspace_id=workspace_id)
    status = ft.Text(storage_label, size=11, color=color('#47747a'))
    title = ft.TextField(label='Название', value=current['title'])
    editor = ft.TextField(value=current.get('content', ''), multiline=True, min_lines=9, max_lines=20,
                         hint_text='Пишите текст или код…', text_style=ft.TextStyle(font_family='monospace'))
    kinds = {'text': 'Текст', 'code': 'Код', 'drawing': 'Рисунок'}
    mode = ft.Dropdown(label='Тип Canvas', value=current['kind'], width=180,
                       options=[ft.DropdownOption(key=k, text=v) for k, v in kinds.items()])
    selection = ft.Dropdown(label='Документ', expand=True)
    picker = ft.FilePicker()
    dimensions = [width - 28, 300]
    paint_color = '#123b43'
    brush_width = 3
    active_stroke = None
    drawing = cv.Canvas(width=width-2, height=300, expand=False)
    drawing.__dict__['_xopilot_fixed_colors'] = True

    def persist(_=None):
        nonlocal current
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

    def changed(_):
        persist()
        page.update()

    title.on_change = changed
    editor.on_change = changed

    def render_drawing(update=True):
        w, h = dimensions
        drawing.shapes = [cv.Path(elements=[cv.Path.MoveTo(points[0][0]*w, points[0][1]*h),
                                *[cv.Path.LineTo(x*w, y*h) for x, y in points[1:]]],
                       paint=ft.Paint(color=stroke['color'], stroke_width=stroke['width'],
                                      style=ft.PaintingStyle.STROKE, stroke_cap=ft.StrokeCap.ROUND))
            for stroke in current.get('strokes', []) if (points := stroke['points'])]
        if update:
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
        active_stroke = {'color': paint_color, 'width': brush_width, 'points': [point(e)]}
        current.setdefault('strokes', []).append(active_stroke)

    def move_stroke(e):
        if active_stroke is not None:
            active_stroke['points'].append(point(e))
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
    draw_area = ft.Column(visible=current['kind'] == 'drawing', controls=[brush,
        ft.Container(bgcolor=ft.Colors.WHITE, border_radius=16, clip_behavior=ft.ClipBehavior.HARD_EDGE,
            border=ft.Border.all(1, color('#a8ddd7')),
            content=ft.GestureDetector(content=drawing, drag_interval=16,
                on_pan_start=start_stroke, on_pan_update=move_stroke, on_pan_end=finish_stroke))])

    def fill_selection():
        selection.options = [ft.DropdownOption(key=item['id'], text=item['title'])
                             for item in canvases.list_documents(chat_id, workspace_id)]
        selection.value = current['id']

    def change_mode(_):
        editor.visible = mode.value != 'drawing'
        draw_area.visible = mode.value == 'drawing'
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

    async def export(_):
        if not persist():
            page.update()
            return
        try:
            name, data = await asyncio.to_thread(canvases.export_document, current)
            path = await picker.save_file(file_name=name, src_bytes=data)
            if path and not page.web:
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
            name, data = await asyncio.to_thread(canvases.export_document, current)
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
            name, data = await asyncio.to_thread(canvases.export_document, current)
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
            controls=[ft.Row(controls=[selection, ft.IconButton(icon=ft.Icons.ADD, tooltip='Новый Canvas', on_click=new_document)]),
                      title, mode, editor, draw_area, status]),
        actions=[ft.TextButton(content='Сохранить', icon=ft.Icons.SAVE_OUTLINED, on_click=changed),
                 ft.TextButton(content='Экспорт', icon=ft.Icons.DOWNLOAD, on_click=export),
                 *([ft.TextButton(content='Локальная копия', icon=ft.Icons.SAVE_ALT, on_click=local_export)]
                   if not page.web or os.environ.get('XOPILOT_LOCAL_WEB') == '1' else []),
                 *([ft.FilledButton(content='В чат', icon=ft.Icons.ATTACH_FILE, on_click=attach)] if on_attach else [])])
