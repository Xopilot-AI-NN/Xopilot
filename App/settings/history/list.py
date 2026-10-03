"""Browse persisted chats and their actual messages from settings."""
import flet as ft
try:
    from ...app.palette import color
    from ...services.chat_store import list_chat_items, load_chat_messages
    from ...services.workspaces import chat_workspace
except ImportError:
    from app.palette import color
    from services.chat_store import list_chat_items, load_chat_messages
    from services.workspaces import chat_workspace


def build_history_list(page, on_select=None):
    search = ft.TextField(hint_text='Поиск по названию или сообщениям', prefix_icon=ft.Icons.SEARCH)
    rows = ft.Column(spacing=8)
    feedback = ft.Text('', size=12, color=color('#47747a'))
    try:
        items = [(cid, title, subtitle, chat_workspace(cid)['name'], load_chat_messages(cid))
                 for cid, title, subtitle, _ in list_chat_items()]
    except Exception as exc:
        items = []
        feedback.value = f'Не удалось прочитать историю: {exc}'

    def preview(identifier, title, messages):
        controls = []
        for message in messages:
            controls.append(ft.Container(padding=14, border_radius=16, bgcolor=color('#f3fffc'),
                content=ft.Column(spacing=6, controls=[
                    ft.Text('Вы' if message.role == 'user' else 'Zephyr', weight=ft.FontWeight.BOLD,
                            size=12, color=color('#087f8c')),
                    ft.Text(message.content, selectable=True, color=color('#123b43')),
                    *([ft.Text('Вложения: ' + ', '.join(name for name, _ in message.attachments),
                               size=11, color=color('#47747a'))] if message.attachments else [])])))
        if not controls:
            controls = [ft.Text('В этом чате пока нет сообщений', color=color('#47747a'))]
        def open_chat(_):
            if on_select:
                page.pop_dialog()
                page.pop_dialog()
                on_select(identifier)
        width = min(640, max(220, (page.width or 800) - 112))
        page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'), title=ft.Text(title, color=color('#123b43')),
            content=ft.ListView(width=width, height=min(450, max(180, (page.height or 720) - 220)),
                                spacing=10, controls=controls),
            actions=[ft.TextButton(content='Закрыть', on_click=lambda _: page.pop_dialog()),
                     *([ft.FilledButton(content='Открыть чат', on_click=open_chat)] if on_select else [])]))

    def render(e=None):
        query = (search.value or '').casefold().strip()
        rows.controls = [ft.Container(bgcolor=color('#f3fffc'), border_radius=16, padding=12,
            ink=True, on_click=lambda _, cid=cid, title=title, messages=messages: preview(cid, title, messages),
            content=ft.Row(controls=[ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE, color=color('#087f8c')),
                ft.Column(expand=True, spacing=4, controls=[
                    ft.Text(title, weight=ft.FontWeight.W_600, color=color('#123b43')),
                    ft.Text(f'{workspace} · {subtitle}', size=11, color=color('#47747a')),
                    ft.Text(messages[-1].content if messages else 'Пустой чат', size=12,
                            max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, color=color('#47747a'))]),
                ft.Icon(ft.Icons.CHEVRON_RIGHT, color=color('#087f8c'))]))
            for cid, title, subtitle, workspace, messages in items
            if not query or query in title.casefold() or any(query in m.content.casefold() for m in messages)]
        if not feedback.value.startswith('Не удалось'):
            feedback.value = f'Чатов: {len(rows.controls)}' if rows.controls else 'Чаты не найдены'
        if e:
            page.update()
    search.on_change = render
    render()
    return ft.Column(spacing=12, controls=[search, feedback, rows])


def build_history_summary():
    return ft.Text('Очистка удалит сообщения только текущего открытого чата.', size=11, color=color('#47747a'))
