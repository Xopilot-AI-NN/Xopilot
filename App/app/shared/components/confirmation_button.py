"""
Файл: /App/app/shared/components/confirmation_button.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Выбор ручного или автоматического подтверждения прямо в чате.
"""
import flet as ft
from ...theme.palette import color, apply_palette
try:
    from ....services import project_tools
except ImportError:
    from services import project_tools


def build_confirmation_button(page,get_chat_id,can_change=lambda:True):
    label=ft.Text('Вручную',size=12)
    icon=ft.Icon(ft.Icons.FACT_CHECK_OUTLINED,size=18)
    compact=False
    def refresh():
        identifier=get_chat_id()
        private=identifier is not None and identifier<0
        mode=project_tools.chat_approval_mode(identifier)
        label.value='Автоматически' if mode=='automatic' else 'Вручную'
        icon.icon=ft.Icons.AUTO_MODE if mode=='automatic' else ft.Icons.FACT_CHECK_OUTLINED
        trigger.tooltip='Подтверждение действий · '+label.value
        trigger.visible=not private
        trigger.width=40 if compact else (150 if mode=='automatic' else 116)
        label.visible=not compact
    def change(value):
        if not can_change():
            page.show_dialog(ft.SnackBar(ft.Text('Смените режим до отправки задачи. Текущие действия ожидают отдельного подтверждения.')))
            return
        identifier=get_chat_id()
        if identifier is None or identifier<0:return
        def save():
            project_tools.set_chat_approval_mode(identifier,value);refresh();page.update()
        if value=='manual' or project_tools.chat_approval_consent(identifier):save();return
        def accept(_):page.pop_dialog();save()
        page.show_dialog(ft.AlertDialog(modal=True,title=ft.Text('Автоматические действия в этом чате?'),
            content=ft.Text('ИИ сможет выполнять действия без отдельных запросов подтверждения. '
                'Команды подключённого проекта запускаются с вашими системными правами и могут обращаться за пределы папки. '
                'На телефоне это также открытие приложений и управление медиаплеером. '
                'Разрешение действует только для этого чата на этом устройстве. Включайте для задач и материалов, которым доверяете.'),
            actions=[ft.TextButton(content='Отмена',on_click=lambda _:page.pop_dialog()),
                     ft.FilledButton(content='Включить автоматически',on_click=accept)]))
    def toggle(_):
        identifier=get_chat_id()
        change('manual' if project_tools.chat_approval_mode(identifier)=='automatic' else 'automatic')
    trigger=ft.Container(height=36,padding=ft.Padding.symmetric(horizontal=10),border_radius=18,
        ink=True,on_click=toggle,bgcolor=color('#dff8f3'),border=ft.Border.all(1,color('#b9eee4')),
        content=ft.Row(spacing=6,controls=[icon,label]))
    def resize(value):
        nonlocal compact
        compact=value;refresh()
    trigger._xopilot_set_compact=resize
    refresh();apply_palette(trigger)
    return trigger,refresh
