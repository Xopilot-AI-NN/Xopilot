"""Persisted history, with confirmed removal of all ordinary chats."""
import flet as ft
try:
    from ...app.palette import color
    from ...app.buttons.actions import action_button
    from ...services.chat_store import clear_all_chats
except ImportError:
    from app.palette import color
    from app.buttons.actions import action_button
    from services.chat_store import clear_all_chats
from .list import build_history_list


def build_history_page(chat_list, on_status, chat_id=None, on_clear=None, page=None, on_select=None, on_delete=None):
    history=build_history_list(page,on_select,on_delete) if page else ft.Column()
    def confirm_clear(_):
        if page is None:
            on_status('Откройте историю в приложении для подтверждения удаления')
            return
        def confirm(_):
            page.pop_dialog()
            try:
                callback=getattr(page,'_xopilot_clear_all_history',None)
                count=callback() if callable(callback) else clear_all_chats()
                getattr(history,'_xopilot_reload',lambda:None)()
                on_status(f'Удалено чатов: {count}')
            except Exception as exc:on_status('Не удалось полностью очистить историю: '+str(exc))
            page.update()
        page.show_dialog(ft.AlertDialog(modal=True,bgcolor=color('#eafffa'),title=ft.Text('Удалить все чаты?'),
            content=ft.Text('Все обычные чаты, их сообщения и черновики будут удалены. Это действие нельзя отменить. '
                            'Защищённые чаты управляются отдельно. Сначала экспортируйте нужные переписки.'),
            actions=[ft.TextButton(content='Отмена',on_click=lambda _:page.pop_dialog()),
                     action_button('Удалить все чаты',on_click=confirm)]))
    return ft.Column(spacing=14,controls=[history,action_button('Очистить историю',icon=ft.Icons.DELETE_OUTLINE,
        secondary=True,on_click=confirm_clear),ft.Text('Очистка удаляет все обычные чаты. Для одного чата используйте кнопку справа от его названия.',
                                                     size=11,color=color('#47747a'))])
