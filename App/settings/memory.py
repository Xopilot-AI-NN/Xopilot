"""Personal memory controls: transparent automatic capture and real CRUD."""
from datetime import datetime
import flet as ft
try:
    from ..services import user_memory as memory
    from ..app.theme.palette import color, modern_input, apply_palette
except ImportError:
    from services import user_memory as memory
    from app.theme.palette import color, modern_input, apply_palette


def build_memory_page(page, on_status=lambda _: None):
    state = memory.read()
    enabled = ft.Switch(label='Использовать память в разговорах', value=state['enabled'])
    automatic = ft.Switch(label='Автоматически сохранять полезные сведения', value=state['automatic'])
    feedback = ft.Text('', size=12, color=color('#47747a'))
    search = modern_input(ft.TextField(hint_text='Поиск в памяти', prefix_icon=ft.Icons.SEARCH))
    rows = ft.Column(spacing=8)

    def refresh(_=None):
        query = (search.value or '').strip().casefold()
        items = [item for item in memory.read()['items'] if query in item['text'].casefold()]
        rows.controls = []
        for item in sorted(items, key=lambda item: item['updated'], reverse=True):
            subtitle = ('Сохранено ИИ' if item['automatic'] else 'Добавлено вручную') + ' · ' + datetime.fromtimestamp(item['updated']).strftime('%d.%m.%Y')
            rows.controls.append(ft.Container(padding=12, border_radius=16, bgcolor=color('#f3fffc'),
                border=ft.Border.all(1, color('#b9eee4')), content=ft.Column(spacing=6, controls=[
                    ft.Text(item['text'], selectable=True, color=color('#123b43')),
                    ft.Row(controls=[ft.Text(subtitle, size=11, expand=True, color=color('#47747a')),
                        ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, tooltip='Изменить запись', on_click=lambda _, item=item: edit(item)),
                        ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip='Удалить запись', on_click=lambda _, item=item: remove(item))])])))
        if not items:
            rows.controls = [ft.Text('Совпадений нет' if query else 'Память пока пуста. Расскажите ИИ о себе или добавьте запись вручную.', color=color('#47747a'))]
        apply_palette(rows)
        page.update()

    def edit(item=None):
        text = modern_input(ft.TextField(label='Что ИИ должен помнить', value=item['text'] if item else '',
            multiline=True, min_lines=3, max_lines=8, max_length=1000, autofocus=True))
        error = ft.Text('', color=color('#b3261e'))
        def save(_):
            try:
                memory.save(text.value or '', item['id'] if item else None)
                page.pop_dialog();refresh();on_status('Память сохранена')
            except Exception as exc:
                error.value = str(exc);page.update()
        page.show_dialog(ft.AlertDialog(title=ft.Text('Изменить память' if item else 'Добавить в память'),
            bgcolor=color('#eafffa'), content=ft.Column(width=500, tight=True, controls=[text, error]),
            actions=[ft.TextButton(content='Отмена', on_click=lambda _: page.pop_dialog()),
                     ft.FilledButton(content='Сохранить', on_click=save)]))

    def remove(item):
        memory.delete(item['id']);refresh();on_status('Запись удалена из памяти')

    def clear(_):
        def confirmed(_):
            memory.clear();page.pop_dialog();refresh();on_status('Память очищена')
        page.show_dialog(ft.AlertDialog(title=ft.Text('Очистить память?'), bgcolor=color('#eafffa'),
            content=ft.Text('Все сохранённые сведения будут удалены. Переписки сохранятся.'),
            actions=[ft.TextButton(content='Отмена', on_click=lambda _: page.pop_dialog()),
                     ft.FilledButton(content='Очистить', on_click=confirmed)]))

    def configure(key, control):
        try:
            memory.configure(**{key: control.value});on_status('Настройки памяти сохранены')
        except Exception as exc:
            control.value = memory.read()[key];feedback.value = str(exc);page.update()
    enabled.on_change = lambda _: configure('enabled', enabled)
    automatic.on_change = lambda _: configure('automatic', automatic)
    search.on_change = refresh
    refresh()
    return ft.Column(spacing=12, controls=[enabled, automatic,
        ft.Text('ИИ сохраняет только явно сообщённые сведения о вас и предпочтения. Можно сказать «Запомни: …». '
                'Автоматический выбор сведений может потребовать дополнительный запрос к выбранной модели. '
                'Память не используется в защищённых и временных чатах. Она хранится в зашифрованной базе '
                'и синхронизируется вместе с профилем, если эта категория включена.', size=12, color=color('#47747a')),
        ft.Row(wrap=True, controls=[ft.OutlinedButton(content='Добавить запись', icon=ft.Icons.ADD, on_click=lambda _: edit()),
                                   ft.TextButton(content='Очистить память', on_click=clear)]),search,feedback,rows])
