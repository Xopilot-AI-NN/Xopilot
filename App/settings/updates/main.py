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


def build_updates_page(on_status) -> ft.Column:
    status = build_update_status()

    async def check(_):
        status.value = "Проверяем обновления..."
        status.update()
        await asyncio.sleep(0.35)
        status.value = "Установлена последняя версия 2.0.0"
        status.update()
        on_status("Проверка обновлений завершена")

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
            ft.Container(padding=ft.padding.Padding.only(left=47), content=status),
        ],
    )
