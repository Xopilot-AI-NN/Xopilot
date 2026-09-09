"""
Файл: /App/settings/account/main.py
Описание: __Страница «Аккаунт»__.
           Профиль пока муляж (облачный аккаунт — фаза 2), а статистика теперь реальная —
           читается из локальной БД через services/stats.py (сообщения точные, токены/часы — приближённые).
"""

import flet as ft

from ..common import section_title

try:
    from ...services.stats import get_stats
except ImportError:
    from services.stats import get_stats

def _stat_card(icon, label: str, value: str, color: str = "#087f8c") -> ft.Container:
    return ft.Container(
        width=134,
        bgcolor="#dff8f3",
        border_radius=12,
        padding=ft.padding.Padding.symmetric(horizontal=12, vertical=10),
        border=ft.border.Border.all(1, "#b9eee4"),
        content=ft.Column(
            spacing=4,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(icon, size=24, color=color),
                ft.Text(label, size=10, color="#47747a", text_align=ft.TextAlign.CENTER, no_wrap=True),
                ft.Text(value, size=15, color="#123b43", weight=ft.FontWeight.BOLD),
            ]
        )
    )

def _format_tokens(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


def build_account_page() -> ft.Column:
    stats = get_stats()
    # Изображение профиля (муляж)
    avatar = ft.Container(
        width=80,
        height=80,
        border_radius=40,
        gradient=ft.LinearGradient(
            begin=ft.alignment.Alignment.TOP_LEFT,
            end=ft.alignment.Alignment.BOTTOM_RIGHT,
            colors=["#00D6A3", "#7657FF"],
        ),
        alignment=ft.alignment.Alignment.CENTER,
        border=ft.border.Border.all(3, "#ffffff"),
        shadow=ft.BoxShadow(blur_radius=10, color="#20000000"),
        content=ft.Icon(ft.Icons.PERSON, color=ft.Colors.WHITE, size=40),
    )

    profile_card = ft.Container(
        padding=ft.padding.Padding.symmetric(horizontal=10, vertical=12),
        bgcolor="#ffffff",
        border_radius=12,
        border=ft.border.Border.all(1, "#b9eee4"),
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
                    ]
                )
            ]
        )
    )

    return ft.Column(
        width=455,
        spacing=10,
        controls=[
            section_title("Профиль"),
            profile_card,
            section_title("Статистика использования ИИ"),
            ft.Row(
                spacing=8,
                wrap=True,
                controls=[
                    _stat_card(ft.Icons.CHAT_BUBBLE_ROUNDED, "Всего сообщений", f"{stats['messages']:,}".replace(",", " ")),
                    _stat_card(ft.Icons.TOKEN, "Токенов потрачено", _format_tokens(stats['tokens'])),
                    _stat_card(ft.Icons.ACCESS_TIME_FILLED_ROUNDED, "Часов с ИИ", f"{stats['hours']:.1f}"),
                ]
            ),
            ft.Container(height=10),
            ft.Divider(height=1, color="#b9eee4"),
            ft.Container(
                padding=ft.padding.Padding.all(4),
                content=ft.Text(
                    "Статистика считается в реальном времени и хранится локально в вашей базе данных. Токены приближённые (по словам ответа, без токенизатора модели).",
                    size=11,
                    color="#47747a",
                    italic=True,
                    width=430,
                )
            )
        ]
    )
