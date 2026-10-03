"""
Файл: /App/settings/account/main.py
Описание: __Страница «Аккаунт»__.
           Профиль пока муляж (облачный аккаунт — фаза 2), а статистика теперь реальная —
           читается из локальной БД через services/stats.py (сообщения точные, токены/часы — приближённые).
"""

import asyncio
import flet as ft
try:
    from ...app.palette import color
except ImportError:
    from app.palette import color

from ..common import section_title

try:
    from ...services.stats import get_stats
    from ...services.db import get_setting, get_db
except ImportError:
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
    stats = get_stats()
    profile_title = ft.Text(get_setting('profile_name', 'Пользователь'), size=22,
                            color=color('#123b43'), weight=ft.FontWeight.BOLD)
    feedback = ft.Text('', color=color('#47747a'), size=12, text_align=ft.TextAlign.CENTER)

    def edit_name(_):
        name = ft.TextField(label='Имя пользователя', value=profile_title.value, autofocus=True)
        def save(_):
            requested = (name.value or '').strip()
            if not requested:
                name.error_text = 'Введите имя'
                page.update()
                return
            try:
                get_db().set_setting('profile_name', requested)
                profile_title.value = requested
                feedback.value = 'Имя сохранено'
                page.pop_dialog()
            except Exception as exc:
                name.error_text = str(exc)
            page.update()
        page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'),
            title=ft.Text('Изменить имя', color=color('#123b43')),
            content=ft.Column(tight=True, width=320, controls=[name]),
            actions=[ft.TextButton(content='Отмена', on_click=lambda _: page.pop_dialog()),
                     ft.FilledButton(content='Сохранить', on_click=save)]))

    avatar = ft.Container(width=76, height=76, border_radius=38,
        gradient=ft.LinearGradient(colors=['#00d6a3', '#7657ff']),
        alignment=ft.Alignment.CENTER, border=ft.Border.all(3, ft.Colors.WHITE),
        content=ft.Icon(ft.Icons.PERSON, color=ft.Colors.WHITE, size=38))
    profile_card = ft.Container(bgcolor=color('#ffffff'), border_radius=20, padding=20,
        border=ft.Border.all(1, color('#b9eee4')),
        content=ft.Row(spacing=16, controls=[avatar,
            ft.Column(expand=True, spacing=6, controls=[
                ft.Row(spacing=4, controls=[ft.Container(expand=True, content=profile_title),
                    ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, tooltip='Изменить имя',
                                  icon_color=color('#087f8c'), on_click=edit_name)]),
                ft.Text('Локальный профиль', color=color('#087f8c'), size=12),
                ft.Text('История хранится на этом устройстве', color=color('#47747a'), size=11)])]))
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
        controls=[profile_card, feedback, section_title('Статистика использования'), cards,
            ft.Text('Размер базы включает журналы WAL и SHM. Материалы и модели хранятся отдельно. '
                    'Токены оцениваются по тексту ответов.', size=11, color=color('#47747a'),
                    text_align=ft.TextAlign.CENTER)])
