"""
Файл: /App/settings/main.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Главное окно настроек__.
           Собирает отдельные страницы персонализации, моделей, истории,
           обновлений и информации о приложении.
"""

import flet as ft
try:
    from ..app.palette import color, apply_palette
except ImportError:
    from app.palette import color, apply_palette

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
    colors=[color("#00c753"), color("#0083e8")],
)


def build_settings_dialog(
    page: ft.Page,
    chat_list: ft.ListView | None = None,
    start_section: int | None = None,
    chat_id: int | None = None,
    on_chat_model_changed=None,
    on_live_model_changed=None,
    on_clear_history=None,
    on_select_chat=None,
) -> ft.AlertDialog:
    status = ft.Text("Изменения применяются сразу", size=11, color=ft.Colors.WHITE, expand=True)

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
            "Локальный профиль",
            ft.Icons.PERSON_OUTLINE,
            "Имя и статистика использования",
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
            lambda: build_history_page(chat_list, set_status, chat_id, on_clear_history, page=page, on_select=on_select_chat),
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

    page_title = ft.Text("Настройки", size=18, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD,
                         max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    page_host = ft.Column(spacing=0, expand=True)

    def select_page(index: int):
        page_host.controls = [apply_palette(sections[index][3]())]
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
        width=max(220, min(750, page.width - 112)) if isinstance(page.width, (int, float)) else 750,
        height=max(220, min(600, page.height - 140)) if isinstance(page.height, (int, float)) else 600,
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=18, vertical=13),
                gradient=BRAND_GRADIENT,
                border_radius=ft.BorderRadius.only(top_left=16, top_right=16),
                content=ft.Column(
                    spacing=8,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                back_button,
                                ft.Column(
                                    expand=True,
                                    spacing=1,
                                    controls=[
                                        ft.Text("Xopilot", size=22, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                                        page_title,
                                    ],
                                ),
                            ],
                        ),
                        ft.Row(controls=[status, ft.IconButton(icon=ft.Icons.CLOSE, icon_color=ft.Colors.WHITE,
                                  tooltip="Закрыть настройки", on_click=lambda _: page.pop_dialog())]),
                    ],
                ),
            ),
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                bgcolor=color("#eafffa"),
                content=ft.Row(controls=[page_host]),
            ),
        ],
    )
    # The brand header has fixed white text and a fixed gradient in every theme.
    # Keep its mounted layout out of recursive value-style replacement.
    content.controls[0].__dict__['_xopilot_fixed_colors'] = True

    return ft.AlertDialog(
        modal=False,
        content=content,
        bgcolor=color("#eafffa"),
        shape=ft.RoundedRectangleBorder(radius=16),
        inset_padding=ft.Padding.symmetric(horizontal=32, vertical=20),
        barrier_color=color("#88000000"),
    )
