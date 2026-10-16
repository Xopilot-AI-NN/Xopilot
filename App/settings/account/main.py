"""
Файл: /App/settings/account/main.py
Описание: __Страница «Аккаунт»__.
           Локальный профиль, статистика и облачный вход с управлением устройствами.
"""

import asyncio
import flet as ft
try:
    from ...app.theme.palette import color, modern_input
    from ...app.menu.buttons.actions import action_button
except ImportError:
    from app.theme.palette import color, modern_input
    from app.menu.buttons.actions import action_button

from ..common import section_title
from .cloud import build_cloud_card

try:
    from ...services import profile
    from ...services.stats import get_stats
    from ...services.db import get_setting, get_db
except ImportError:
    from services import profile
    from services.stats import get_stats
    from services.db import get_setting, get_db


def _stat_card(icon, label: str, value: str, accent: str | None = None) -> ft.Container:
    # Создаёт небольшую карточку со статистикой.
    return ft.Container(
        width=134,
        bgcolor=color("#dff8f3"),
        border_radius=12,
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        border=ft.Border.all(1, color("#b9eee4")),
        content=ft.Column(
            spacing=4,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(icon, size=24, color=accent or color("#087f8c")),
                ft.Text(label, size=10, color=color("#47747a"), text_align=ft.TextAlign.CENTER, no_wrap=True),
                ft.Text(value, size=15, color=color("#123b43"), weight=ft.FontWeight.BOLD),
            ],
        ),
    )


def _format_tokens(n: int) -> str:
    # Сокращает большие значения токенов для карточки.
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


def _format_app_time(seconds: float) -> str:
    # Переводит время работы приложения в удобные единицы.
    minutes = seconds / 60
    hours = minutes / 60
    days = hours / 24
    weeks = days / 7

    if days >= 365.25:
        return f"{days / 365.25:.1f} лет"
    if weeks >= 1:
        return f"{weeks:.1f} недель"
    if days >= 1:
        return f"{days:.1f} дней"
    if hours >= 1:
        return f"{hours:.1f} часов"
    return f"{max(1, round(minutes))} минут"


def _format_bytes(value):
    for unit in ('Б', 'КБ', 'МБ', 'ГБ'):
        if value < 1024 or unit == 'ГБ':
            return f'{value:.1f} {unit}' if unit != 'Б' else f'{value} Б'
        value /= 1024


def build_account_page(page: ft.Page) -> ft.Column:
    try:
        from ...services.platforms import is_android, compact_layout
    except ImportError:
        from services.platforms import is_android, compact_layout
    compact = compact_layout(getattr(page, 'width', None))
    stats = get_stats()
    profile_title = ft.Text(profile.read()['name'], size=20 if compact else 22,
                            color=color('#123b43'), weight=ft.FontWeight.BOLD)
    feedback = ft.Text('', visible=False, color=color('#47747a'), size=12, text_align=ft.TextAlign.CENTER)

    def edit_name(_):
        name = modern_input(ft.TextField(label='Имя пользователя', value=profile_title.value, autofocus=True))
        def save(_):
            requested = (name.value or '').strip()
            if not requested:
                name.error_text = 'Введите имя'
                page.update()
                return
            try:
                profile.update(name=requested)
                profile_title.value = requested
                feedback.value = 'Имя сохранено'
                feedback.visible=True
                page.pop_dialog()
            except Exception as exc:
                name.error_text = str(exc)
            page.update()
        page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'),
            title=ft.Text('Изменить имя', color=color('#123b43')),
            content=ft.Column(tight=True, width=320, controls=[name]),
            actions=[ft.TextButton(content='Отмена', on_click=lambda _: page.pop_dialog()),
                     action_button('Сохранить', on_click=save)]))

    picker=ft.FilePicker()
    async def choose_avatar(_):
        try:
            if is_android() and not page.web:
                try:
                    from ...services.mobile_documents import pick_avatar
                except ImportError:
                    from services.mobile_documents import pick_avatar
                result = await pick_avatar()
                if result and result.get('profile'):
                    refresh_profile();feedback.value='Аватарка сохранена';feedback.visible=True;page.update()
                return
            selected=await picker.pick_files(dialog_title='Выберите аватарку',allow_multiple=False,
                file_type=ft.FilePickerFileType.CUSTOM,allowed_extensions=['jpg','jpeg','png','webp'],with_data=bool(page.web) or is_android())
            if not selected:return
            chosen=selected[0]
            await asyncio.to_thread(profile.set_avatar,path=chosen.path,data=chosen.bytes)
            refresh_profile();feedback.value='Аватарка сохранена';feedback.visible=True;page.update()
        except Exception as exc:feedback.value=str(exc);feedback.visible=True;page.update()
    avatar_size = 56 if compact else 76
    avatar = ft.Container(width=avatar_size,height=avatar_size,border_radius=avatar_size/2,clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        gradient=ft.LinearGradient(colors=['#00d6a3','#7657ff']),alignment=ft.Alignment.CENTER,
        border=ft.Border.all(1,color('#a8ddd7')),ink=True,tooltip='Изменить аватарку',on_click=choose_avatar)
    def refresh_profile():
        import base64
        data=profile.read();profile_title.value=data['name']
        avatar.content=ft.Image(src=base64.b64decode(data['avatar']),width=avatar_size,height=avatar_size,fit=ft.BoxFit.COVER,exclude_from_semantics=True) if data['avatar'] else ft.Icon(ft.Icons.PERSON,color=ft.Colors.WHITE,size=38)
    refresh_profile()
    page._xopilot_profile_refresh=refresh_profile
    profile_card = ft.Container(bgcolor=color('#f3fffc'), border_radius=22, padding=12 if compact else 20,
        content=ft.Row(spacing=10 if compact else 16, controls=[avatar,
            ft.Column(expand=True, spacing=6, controls=[
                ft.Row(spacing=4, controls=[ft.Container(expand=True, content=profile_title),
                    ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, tooltip='Изменить имя',
                                  icon_color=color('#087f8c'), on_click=edit_name)]),
                ft.Text('Ваш профиль · нажмите на фото, чтобы изменить', color=color('#087f8c'), size=12),
                ft.Text('Имя и аватарка синхронизируются при включённой синхронизации профиля', color=color('#47747a'), size=11)])]))
    values = [
        (ft.Icons.FORUM_OUTLINED, 'Чатов', str(stats.get('chats', 0))),
        (ft.Icons.CHAT_BUBBLE_ROUNDED, 'Сообщений', f"{stats['messages']:,}".replace(',', ' ')),
        (ft.Icons.TOKEN, 'Примерно токенов', _format_tokens(stats['tokens'])),
        (ft.Icons.ACCESS_TIME_FILLED_ROUNDED, 'Время в Xopilot', _format_app_time(stats['app_seconds'])),
        (ft.Icons.STORAGE_ROUNDED, 'Размер базы', _format_bytes(stats.get('db_bytes', 0))),
    ]
    cards = ft.Row(wrap=True, spacing=12, run_spacing=12, alignment=ft.MainAxisAlignment.CENTER,
                  controls=[_stat_card(*value) for value in values])
    return ft.Column(spacing=16, horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[profile_card, feedback, build_cloud_card(page), section_title('Статистика использования'), cards,
            ft.Text('Размер базы включает журналы WAL и SHM. Материалы и модели хранятся отдельно. '
                    'Токены оцениваются по тексту ответов.', size=11, color=color('#47747a'),
                    text_align=ft.TextAlign.CENTER)])
