"""
Файл: /App/settings/main.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Главное окно настроек__.
           Собирает отдельные страницы персонализации, безопасности,
           истории, обновлений и информации о приложении.
           Отвечает только за навигацию и общую оболочку окна.
"""

import flet as ft
from typing import cast

from .abaut.main import build_about_page
from .buttons.back import build_back_button
from .common import section_title
from .buttons.navigation import build_navigation_button
from .encryption_and_security.main import build_security_page
from .history.main import build_history_page
from .personalizations.main import build_personalizations_page
from .updates.main import build_updates_page


BRAND_GRADIENT = ft.LinearGradient(
    begin=ft.alignment.Alignment.TOP_LEFT,
    end=ft.alignment.Alignment.BOTTOM_RIGHT,
    colors=["#00c753", "#0083e8"],
)


def build_settings_dialog(
    page: ft.Page,
    chat_list: ft.ListView | None = None,
) -> ft.AlertDialog:
    status = ft.Text("Изменения применяются сразу", size=11, color="#dff8f3")

    def set_status(text: str):
        status.value = text
        status.update()

    detail_pages = [
        build_personalizations_page(page, set_status),
        build_security_page(set_status),
        build_history_page(chat_list, set_status),
        build_updates_page(set_status),
        build_about_page(),
    ]
    labels = [
        ("Внешний вид", ft.Icons.DARK_MODE_OUTLINED),
        ("Безопасность", ft.Icons.LOCK_OUTLINE),
        ("История", ft.Icons.HISTORY),
        ("Обновления", ft.Icons.SYSTEM_UPDATE_OUTLINED),
        ("О программе", ft.Icons.INFO_OUTLINE),
    ]

    page_title = ft.Text("Настройки", size=20, color="#123b43", weight=ft.FontWeight.BOLD)
    page_host = ft.Column(spacing=0)

    def select_page(index: int):
        page_host.controls = [detail_pages[index]]
        page_title.value = labels[index][0]
        back_button.visible = True
        page.update()

    def show_home(_=None):
        page_host.controls = [home_page]
        page_title.value = "Настройки"
        back_button.visible = False
        page.update()

    home_page = ft.Column(
        spacing=2,
        controls=[
            section_title("Параметры приложения"),
            *[
                build_navigation_button(
                    icon,
                    label,
                    (
                        "Тема оформления и язык интерфейса"
                        if index == 0
                        else "Настройки защиты локальных чатов"
                        if index == 1
                        else "Удаление и управление сообщениями"
                        if index == 2
                        else "Версия и обновления приложения"
                        if index == 3
                        else "Версия, описание и разработчик"
                    ),
                    lambda _, selected=index: select_page(selected),
                )
                for index, (label, icon) in enumerate(labels)
            ],
        ],
    )
    page_host.controls = [home_page]
    back_button = build_back_button(show_home)

    content = ft.Column(
        width=650,
        height=500,
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Container(
                height=76,
                padding=ft.padding.Padding.symmetric(horizontal=18, vertical=13),
                gradient=BRAND_GRADIENT,
                border_radius=ft.border_radius.BorderRadius.only(top_left=16, top_right=16),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                back_button,
                                ft.Column(
                                    spacing=1,
                                    controls=[
                                        ft.Text("Xopilot", size=22, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                                        page_title,
                                    ],
                                ),
                            ],
                        ),
                        status,
                    ],
                ),
            ),
            ft.Container(
                padding=ft.padding.Padding.symmetric(horizontal=12, vertical=8),
                bgcolor="#eafffa",
                content=ft.Row(
                    controls=[page_host],
                ),
            ),
        ],
    )

    return ft.AlertDialog(
        modal=False,
        content=content,
        bgcolor="#eafffa",
        shape=ft.RoundedRectangleBorder(radius=16),
        inset_padding=ft.padding.Padding.symmetric(horizontal=32, vertical=20),
        barrier_color="#88000000",
        actions=[ft.TextButton("Закрыть", on_click=lambda _: page.pop_dialog())],
        actions_alignment=ft.MainAxisAlignment.END,
    )
