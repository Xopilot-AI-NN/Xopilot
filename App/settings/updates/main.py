"""
Файл: /App/settings/updates/main.py
Описание: __Страница обновлений__.
           Показывает текущую версию и запускает проверку обновлений.
"""

import asyncio
import flet as ft

from ..common import section_title, setting_row
from .buttons.check import build_check_button
from .status import build_update_status

try:
    from ...services.updates import check_updates
except ImportError:
    from services.updates import check_updates


def build_updates_page(on_status) -> ft.Column:
    status = build_update_status()

    async def check(_):
        status.value = "Проверяем обновления..."
        status.update()
        try:
            status.value = await asyncio.to_thread(check_updates)
        except Exception as exc:
            status.value = f"Не удалось проверить обновления: {exc}"
        status.update()
        on_status(status.value)

    return ft.Column(
        spacing=2,
        controls=[
            section_title("Система"),
            setting_row(
                ft.Icons.SYSTEM_UPDATE_OUTLINED,
                "Обновления",
                "Проверить актуальность версии приложения",
                build_check_button(check),
            ),
            ft.Container(padding=ft.Padding.only(left=47), content=status),
        ],
    )
