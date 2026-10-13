"""Explicit model catalog for the composer, including installation and API setup."""
import inspect
import flet as ft
from .brand import brand_gradient
from ..palette import color, outline_color
from ..api_settings import open_api_settings
from ..model_download import ModelDownloadPanel
try:
    from ...services import api_chat
    from ...services.llm import list_local_models, execution_info, get_loaded_model
    from ...services.model_settings import get_selected_chat_model, model_display_name
    from ...services.model_installer import DOWNLOADABLE_MODELS, install_model
    from ...services.platforms import is_android
except ImportError:
    from services import api_chat
    from services.llm import list_local_models, execution_info, get_loaded_model
    from services.model_settings import get_selected_chat_model, model_display_name
    from services.model_installer import DOWNLOADABLE_MODELS, install_model
    from services.platforms import is_android
import asyncio


def build_model_button(on_select=None, *, get_agent_level=None, on_agent_level=None):
    label = ft.Text('Модель', size=12, color=ft.Colors.WHITE, max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS, expand=True)
    trigger = ft.Container(width=154, height=48 if is_android() else 40, border_radius=24 if is_android() else 20, ink=True,
        gradient=brand_gradient('ai'), border=ft.Border.all(2, outline_color()), padding=8,
        tooltip='Выбор модели', content=ft.Row(spacing=5, controls=[
            ft.Icon(ft.Icons.SMART_TOY_OUTLINED, color=ft.Colors.WHITE, size=18), label,
            ft.Icon(ft.Icons.EXPAND_MORE, color=ft.Colors.WHITE, size=16)]))
    trigger._xopilot_fixed_colors = True
    compact = False
    narrow = False
    last_private = False
    robot, arrow = trigger.content.controls[0], trigger.content.controls[-1]

    def refresh(update=False, private=False):
        nonlocal last_private
        last_private = private
        trigger.width = 154
        label.value = 'API · ' + api_chat.configuration().get('model', '') if api_chat.is_api_selected() and not private else model_display_name(get_selected_chat_model())
        trigger.tooltip = 'Выбор модели · ' + label.value
        if get_agent_level:
            trigger.tooltip += '\nАгентность: ' + {'off': 'выключена', 'auto': 'автоматически', 'low': 'низкая', 'medium': 'средняя', 'high': 'высокая'}.get(get_agent_level(), 'выключена')
        if not api_chat.is_api_selected() or private:
            state = execution_info()
            if get_loaded_model() == get_selected_chat_model() and state['backend']:
                trigger.width = 190
                label.value += ' · ' + state['backend'].upper()
                trigger.tooltip += '\n' + state['backend'].upper() + (' · ' + state['reason'] if state['reason'] else '')
        if compact:
            # Keep a useful name visible instead of the long empty-state text.
            label.value = ('API' if api_chat.is_api_selected() and not private else
                           model_display_name(get_selected_chat_model()) if get_selected_chat_model() else 'Модель')
            if narrow:
                label.value = label.value.replace('Gemma4-', '')
            trigger.width = None
            trigger.expand = True
        if get_agent_level and get_agent_level() != 'off':
            label.value += ' · ' + {'auto':'Авто', 'low':'Низк.', 'medium':'Средн.', 'high':'Высок.'}.get(get_agent_level(), '')
        if update:
            trigger.update()

    async def show(e):
        page = e.page
        feedback = ft.Text('Выберите установленную модель или скачайте её.', size=12, color=color('#47747a'))
        state = execution_info()
        if state['backend'] and get_loaded_model():
            feedback.value = model_display_name(get_loaded_model()) + ' · ' + state['backend'].upper()
            if state['reason']:
                feedback.value += '\n' + state['reason']
        rows = ft.Column(spacing=10, tight=True)
        busy = False
        async def choose(model):
            nonlocal busy
            if busy:
                return
            if model.filename not in list_local_models():
                async def ready():
                    page.pop_dialog()
                    await choose(model)
                page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'),
                    title=ft.Text(model.name, color=color('#123b43')),
                    content=ft.Column(width=max(230, min(380, page.width - 112)), tight=True, controls=[
                        ft.Text(model.size_label + ' · загрузка продолжится после обрыва сети', size=12, color=color('#47747a')),
                        ModelDownloadPanel(model, ready)]),
                    actions=[ft.TextButton(content='Закрыть', on_click=lambda _: page.pop_dialog())]))
                return
            if on_select:
                result = on_select(model.filename)
                if inspect.isawaitable(result):
                    result = await result
                if result is False:
                    return
            page.pop_dialog()
            refresh(True)
        def local_row(model):
            async def click(_):
                await choose(model)
            installed = model.filename in list_local_models()
            return ft.Container(padding=14, border_radius=16, bgcolor=color('#f3fffc'),
                border=ft.Border.all(1, color('#a8ddd7')), ink=True, on_click=click,
                content=ft.Row(controls=[ft.Icon(ft.Icons.SMART_TOY_OUTLINED, color=color('#087f8c')),
                    ft.Column(expand=True, spacing=3, controls=[ft.Text(model.name, color=color('#123b43'), weight=ft.FontWeight.W_600),
                        ft.Text('На устройстве' if installed else f'Скачать · {model.size_label}', size=11, color=color('#47747a'))]),
                    ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE if installed else ft.Icons.DOWNLOAD, color=color('#087f8c'))]))
        rows.controls = [ft.Container(padding=14, border_radius=16, bgcolor=color('#f3fffc'), border=ft.Border.all(1, color('#a8ddd7')),
            content=ft.Row(controls=[ft.Icon(ft.Icons.CONSTRUCTION, color=color('#47747a')),
                ft.Text('Zephyr Micro · в разработке', color=color('#47747a'), expand=True)])),
            *[local_row(model) for model in DOWNLOADABLE_MODELS.values()],
            ft.Container(padding=14, border_radius=16, bgcolor=color('#f3fffc'), border=ft.Border.all(1, color('#a8ddd7')),
                ink=True, on_click=lambda _: open_api_settings(page, on_saved=lambda: refresh(True)),
                content=ft.Row(controls=[ft.Icon(ft.Icons.API, color=color('#087f8c')),
                    ft.Text('API · настроить подключение', color=color('#123b43'), expand=True)]))]
        options = []
        if get_agent_level and on_agent_level:
            level = ft.Dropdown(label='Агентность', value=get_agent_level(),
                options=[ft.DropdownOption(key=k, text=v) for k, v in
                    [('off', 'Выключена'), ('auto', 'Автоматически'), ('low', 'Низкая'), ('medium', 'Средняя'), ('high', 'Высокая')]])
            def change_level(_):
                on_agent_level(level.value)
                refresh(True)
            level.on_select = change_level
            options = [level, ft.Text('Уровень действий ИИ: поиск в библиотеке, чтение материалов и работа с Canvas.', size=11, color=color('#47747a'))]
        page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'), shape=ft.RoundedRectangleBorder(radius=22),
            title=ft.Text('Модель чата', color=color('#123b43')),
            content=ft.Column(width=max(230, min(380, page.width - 112)), height=min(390, page.height - 180), scroll=ft.ScrollMode.AUTO, controls=[rows, *options, feedback]),
            actions=[ft.TextButton(content='Закрыть', on_click=lambda _: page.pop_dialog())]))
    trigger.on_click = show
    def set_compact(value):
        nonlocal compact
        compact = value
        trigger.expand = True if value else None
        trigger.height = 40 if value else (48 if is_android() else 40)
        trigger.padding = ft.Padding.symmetric(horizontal=7 if value else 8)
        robot.visible = not value
        arrow.size = 14 if value else 16
        refresh(private=last_private)
    trigger._xopilot_set_compact = set_compact
    def set_narrow(value):
        nonlocal narrow
        if narrow != value:
            narrow = value
            refresh(private=last_private)
    trigger._xopilot_set_narrow = set_narrow
    refresh()
    return trigger, refresh
