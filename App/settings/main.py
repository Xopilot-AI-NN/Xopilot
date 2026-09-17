"""
Файл: /App/settings/main.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Главное окно настроек__.
           Собирает отдельные страницы персонализации, моделей, истории,
           обновлений и информации о приложении.
"""

import flet as ft

from .abaut.main import build_about_page
from .account.main import build_account_page
from .buttons.back import build_back_button
from .common import section_title
from .buttons.navigation import build_navigation_button
from .history.main import build_history_page
from .models.main import build_models_page
from .personalizations.main import build_personalizations_page
from .updates.main import build_updates_page


BRAND_GRADIENT = ft.LinearGradient(
    begin=ft.Alignment.TOP_LEFT,
    end=ft.Alignment.BOTTOM_RIGHT,
    colors=["#00c753", "#0083e8"],
)


def build_settings_dialog(
    page: ft.Page,
    chat_list: ft.ListView | None = None,
    start_section: int | None = None,
    chat_id: int | None = None,
    on_chat_model_changed=None,
    on_live_model_changed=None,
) -> ft.AlertDialog:
    status = ft.Text("Изменения применяются сразу", size=11, color="#dff8f3")

    def set_status(text: str):
        status.value = text
        status.update()

    def refresh_model_surfaces():
        if on_chat_model_changed is not None:
            on_chat_model_changed()
        if on_live_model_changed is not None:
            on_live_model_changed()

    # Страницы строятся при открытии раздела. Поэтому после установки модели/голоса
    # «Персонализация» сразу увидит новые локальные файлы без перезапуска приложения.
    sections = [
        (
            "Аккаунт",
            ft.Icons.PERSON_OUTLINE,
            "Профиль, тариф и статистика ИИ",
            lambda: build_account_page(page),
        ),
        (
            "Персонализация",
            ft.Icons.TUNE,
            "Тема, язык, модели ИИ и голос Live",
            lambda: build_personalizations_page(
                page,
                set_status,
                on_chat_model_changed=on_chat_model_changed,
                on_live_model_changed=on_live_model_changed,
            ),
        ),
        (
            "Модели",
            ft.Icons.DOWNLOAD_OUTLINED,
            "Загрузка Gemma 4 и голосов Live",
            lambda: build_models_page(
                page,
                set_status,
                on_models_changed=refresh_model_surfaces,
            ),
        ),
        (
            "История",
            ft.Icons.HISTORY,
            "Удаление и управление сообщениями",
            lambda: build_history_page(chat_list, set_status, chat_id),
        ),
        (
            "Обновления",
            ft.Icons.SYSTEM_UPDATE_OUTLINED,
            "Версия и обновления приложения",
            lambda: build_updates_page(set_status),
        ),
        (
            "О программе",
            ft.Icons.INFO_OUTLINE,
            "Версия, описание и разработчик",
            build_about_page,
        ),
    ]

    page_title = ft.Text("Настройки", size=20, color="#123b43", weight=ft.FontWeight.BOLD)
    page_host = ft.Column(spacing=0, expand=True)

    def select_page(index: int):
        page_host.controls = [sections[index][3]()]
        page_title.value = sections[index][0]
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
                    subtitle,
                    lambda _, selected=index: select_page(selected),
                )
                for index, (label, icon, subtitle, _builder) in enumerate(sections)
            ],
        ],
    )
    page_host.controls = [home_page]
    back_button = build_back_button(show_home)

    if start_section is not None:
        select_page(start_section)

    content = ft.Column(
        width=750,
        height=600,
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Container(
                height=76,
                padding=ft.Padding.symmetric(horizontal=18, vertical=13),
                gradient=BRAND_GRADIENT,
                border_radius=ft.BorderRadius.only(top_left=16, top_right=16),
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
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                bgcolor="#eafffa",
                content=ft.Row(controls=[page_host]),
            ),
        ],
    )

    return ft.AlertDialog(
        modal=False,
        content=content,
        bgcolor="#eafffa",
        shape=ft.RoundedRectangleBorder(radius=16),
        inset_padding=ft.Padding.symmetric(horizontal=32, vertical=20),
        barrier_color="#88000000",
    )
