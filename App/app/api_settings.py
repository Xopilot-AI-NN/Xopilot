"""Connection settings stored in the encrypted local database."""
import flet as ft
from .palette import color
try:
    from ..services import api_chat
except ImportError:
    from services import api_chat


def open_api_settings(page, on_saved=None):
    config = api_chat.configuration()
    url = ft.TextField(label='URL API', hint_text='https://example.com/v1', value=config.get('url', ''))
    model = ft.TextField(label='Модель API', hint_text='Идентификатор модели у провайдера', value=config.get('model', ''))
    key = ft.TextField(label='API-ключ', password=True, can_reveal_password=True, value=config.get('key', ''))
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
        content=ft.Column(width=max(230, min(420, page.width - 112)), height=min(360, page.height - 180), scroll=ft.ScrollMode.AUTO, spacing=14, controls=[url, model, key, feedback]),
        actions=[ft.TextButton(content='Отмена', on_click=lambda _: page.pop_dialog()),
                 ft.FilledButton(content='Сохранить и выбрать API', on_click=save)]))
