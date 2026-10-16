"""
Файл: /App/app/settings/api_settings.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Компонент api_settings интерфейса Xopilot.
"""
"""Connection settings stored in the encrypted local database."""
import flet as ft
from ..theme.palette import color
try:
    from ...services import api_chat
except ImportError:
    from services import api_chat


def open_api_settings(page, on_saved=None):
    config = api_chat.configuration()
    url = ft.TextField(label='URL API', hint_text='https://example.com/v1', value=config.get('url', ''))
    model = ft.TextField(label='Модель API', hint_text='Идентификатор модели у провайдера', value=config.get('model', ''))
    key = ft.TextField(label='API-ключ', password=True, can_reveal_password=True, value=config.get('key', ''))
    provider = ft.Dropdown(label='Провайдер', value=api_chat.provider_for(config),
        options=[ft.DropdownOption(key=k, text=v[0]) for k, v in api_chat.PROVIDERS.items()])
    drafts = {provider.value: dict(config)}
    previous = provider.value
    def change_provider(_):
        nonlocal previous
        drafts[previous] = {'url': url.value, 'model': model.value, 'key': key.value}
        selected = drafts.get(provider.value, {})
        url.value = selected.get('url', api_chat.PROVIDERS[provider.value][1])
        key.value = selected.get('key', '')
        model.value = selected.get('model', '')
        model.hint_text = 'Например, gemini-3.8-flash' if provider.value == 'google' else 'Идентификатор модели у провайдера'
        previous = provider.value
        page.update()
    provider.on_select = change_provider
    feedback = ft.Text('Запросы, история текущего чата и выбранные материалы отправляются указанному API. '
                       'Ключ сохраняется в зашифрованной локальной базе. Live использует локальную модель.',
                       size=12, color=color('#47747a'))
    def save(_):
        try:
            api_chat.save_configuration({'url': url.value, 'model': model.value, 'key': key.value})
            api_chat.select_api()
            page.pop_dialog()
            if on_saved:
                on_saved()
        except Exception as exc:
            feedback.value = str(exc)
            feedback.color = color('#b3261e')
        page.update()
    page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'), shape=ft.RoundedRectangleBorder(radius=22),
        title=ft.Text('Подключение API', color=color('#123b43')),
        content=ft.Column(width=max(230, min(420, page.width - 112)), height=min(420, page.height - 180), scroll=ft.ScrollMode.AUTO, spacing=14, controls=[provider, url, model, key, feedback]),
        actions=[ft.TextButton(content='Отмена', on_click=lambda _: page.pop_dialog()),
                 ft.FilledButton(content='Подключить', on_click=save)]))
