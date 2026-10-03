"""Explicit model catalog for the composer, including installation and API setup."""
import inspect
import flet as ft
from .brand import brand_gradient
from ..palette import color
from ..api_settings import open_api_settings
try:
    from ...services import api_chat
    from ...services.llm import list_local_models
    from ...services.model_settings import get_selected_chat_model, model_display_name
    from ...services.model_installer import DOWNLOADABLE_MODELS, install_model
except ImportError:
    from services import api_chat
    from services.llm import list_local_models
    from services.model_settings import get_selected_chat_model, model_display_name
    from services.model_installer import DOWNLOADABLE_MODELS, install_model
import asyncio


def build_model_button(on_select=None):
    label = ft.Text('Модель', size=12, color=ft.Colors.WHITE, max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS, expand=True)
    trigger = ft.Container(width=154, height=40, border_radius=20, ink=True,
        gradient=brand_gradient(), border=ft.Border.all(2, ft.Colors.WHITE), padding=8,
        tooltip='Выбор модели', content=ft.Row(spacing=5, controls=[
            ft.Icon(ft.Icons.SMART_TOY_OUTLINED, color=ft.Colors.WHITE, size=18), label,
            ft.Icon(ft.Icons.EXPAND_MORE, color=ft.Colors.WHITE, size=16)]))
    trigger._xopilot_fixed_colors = True

    def refresh(update=False, private=False):
        label.value = 'API · ' + api_chat.configuration().get('model', '') if api_chat.is_api_selected() and not private else model_display_name(get_selected_chat_model())
        trigger.tooltip = 'Выбор модели · ' + label.value
        if update:
            trigger.update()

    async def show(e):
        page = e.page
        feedback = ft.Text('Выберите установленную модель или скачайте её.', size=12, color=color('#47747a'))
        rows = ft.Column(spacing=10, tight=True)
        busy = False
        async def choose(model):
            nonlocal busy
            if busy:
                return
            if model.filename not in list_local_models():
                busy = True
                feedback.value = f'Скачиваю {model.name} ({model.size_label})…'
                for row in rows.controls:
                    row.disabled = True
                page.update()
                try:
                    await asyncio.to_thread(install_model, model.id)
                except Exception as exc:
                    feedback.value = f'Не удалось скачать модель: {exc}'
                    feedback.color = color('#b3261e')
                    return
                finally:
                    busy = False
                    for row in rows.controls:
                        row.disabled = False
                    page.update()
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
                ft.Text('Zephyr Micro · в разработке', color=color('#47747a'))])),
            *[local_row(model) for model in DOWNLOADABLE_MODELS.values()],
            ft.Container(padding=14, border_radius=16, bgcolor=color('#f3fffc'), border=ft.Border.all(1, color('#a8ddd7')),
                ink=True, on_click=lambda _: open_api_settings(page, on_saved=lambda: refresh(True)),
                content=ft.Row(controls=[ft.Icon(ft.Icons.API, color=color('#087f8c')),
                    ft.Text('API · настроить подключение', color=color('#123b43'))]))]
        page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'), shape=ft.RoundedRectangleBorder(radius=22),
            title=ft.Text('Модель чата', color=color('#123b43')),
            content=ft.Column(width=max(230, min(380, page.width - 112)), height=min(390, page.height - 180), scroll=ft.ScrollMode.AUTO, controls=[rows, feedback]),
            actions=[ft.TextButton(content='Закрыть', on_click=lambda _: page.pop_dialog())]))
    trigger.on_click = show
    refresh()
    return trigger, refresh
