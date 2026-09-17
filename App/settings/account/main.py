"""
Файл: /App/settings/account/main.py
Описание: __Страница «Аккаунт»__.
           Профиль пока муляж (облачный аккаунт — фаза 2), а статистика теперь реальная —
           читается из локальной БД через services/stats.py (сообщения точные, токены/часы — приближённые).
"""

import asyncio
import flet as ft

from ..common import section_title

try:
    from ...services.stats import get_stats
except ImportError:
    from services.stats import get_stats


def _stat_card(icon, label: str, value: str, color: str = "#087f8c") -> ft.Container:
    # Создаёт небольшую карточку со статистикой.
    return ft.Container(
        width=134,
        bgcolor="#dff8f3",
        border_radius=12,
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        border=ft.Border.all(1, "#b9eee4"),
        content=ft.Column(
            spacing=4,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(icon, size=24, color=color),
                ft.Text(label, size=10, color="#47747a", text_align=ft.TextAlign.CENTER, no_wrap=True),
                ft.Text(value, size=15, color="#123b43", weight=ft.FontWeight.BOLD),
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


def build_account_page(page: ft.Page) -> ft.Column:
    # Собирает страницу аккаунта и статистики.
    stats = get_stats()
    app_time = ft.Text(
        _format_app_time(stats["app_seconds"]),
        size=15,
        color="#123b43",
        weight=ft.FontWeight.BOLD,
    )

    time_card = ft.Container(
        width=134,
        bgcolor="#dff8f3",
        border_radius=12,
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        border=ft.Border.all(1, "#b9eee4"),
        content=ft.Column(
            spacing=4,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.ACCESS_TIME_FILLED_ROUNDED, size=24, color="#087f8c"),
                ft.Text("Время в Xopilot", size=10, color="#47747a", text_align=ft.TextAlign.CENTER, no_wrap=True),
                app_time,
            ],
        ),
    )

    async def refresh_time():
        # Обновляет отображаемое время во время работы приложения.
        while True:
            await asyncio.sleep(10)
            try:
                stats_now = get_stats()
                app_time.value = _format_app_time(stats_now["app_seconds"])
                app_time.update()
            except Exception:
                break

    page.run_task(refresh_time)

    avatar = ft.Container(
        width=80,
        height=80,
        border_radius=40,
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=["#00D6A3", "#7657FF"],
        ),
        alignment=ft.Alignment.CENTER,
        border=ft.Border.all(3, "#ffffff"),
        shadow=ft.BoxShadow(blur_radius=10, color="#20000000"),
        content=ft.Icon(ft.Icons.PERSON, color=ft.Colors.WHITE, size=40),
    )

    profile_card = ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=12),
        bgcolor="#ffffff",
        border_radius=12,
        border=ft.Border.all(1, "#b9eee4"),
        content=ft.Row(
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                avatar,
                ft.Column(
                    spacing=4,
                    controls=[
                        ft.Text("Developer", size=18, color="#123b43", weight=ft.FontWeight.BOLD),
                        ft.Text("Локальный режим (без облака)", size=12, color="#087f8c", weight=ft.FontWeight.W_500),
                        ft.Text("Аккаунт появится в фазе 2 (облако)", size=10, color="#47747a"),
                    ],
                ),
            ],
        ),
    )

    return ft.Column(
        width=455,
        spacing=10,
        controls=[
            section_title("Профиль"),
            profile_card,
            section_title("Статистика использования"),
            ft.Row(
                spacing=8,
                wrap=True,
                controls=[
                    _stat_card(ft.Icons.CHAT_BUBBLE_ROUNDED, "Всего сообщений", f"{stats['messages']:,}".replace(",", " ")),
                    _stat_card(ft.Icons.TOKEN, "Токенов потрачено", _format_tokens(stats['tokens'])),
                    time_card,
                ],
            ),
            ft.Container(height=10),
            ft.Divider(height=1, color="#b9eee4"),
            ft.Container(
                padding=ft.Padding.all(4),
                content=ft.Text(
                    "Время считается с момента запуска Xopilot и хранится локально в базе данных. Счётчик обновляется автоматически.",
                    size=11,
                    color="#47747a",
                    italic=True,
                    width=430,
                ),
            ),
        ],
    )