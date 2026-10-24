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
    from ..app.theme.palette import color, apply_palette
    from ..app.menu.buttons.brand import style_brand_button
    from ..services.platforms import compact_layout
except ImportError:
    from app.theme.palette import color, apply_palette
    from app.menu.buttons.brand import style_brand_button
    from services.platforms import compact_layout

from .abaut.main import build_about_page
from .account.main import build_account_page
from .buttons.back import build_back_button
from .common import section_title
from .buttons.navigation import build_navigation_button
from .history.main import build_history_page
from .models.main import build_models_page
from .personalizations.main import build_personalizations_page
from .updates.main import build_updates_page
from .memory import build_memory_page
try:
    from ..services import navigation, platforms
except ImportError:
    from services import navigation, platforms


def build_settings_dialog(
    page: ft.Page,
    chat_list: ft.ListView | None = None,
    start_section: int | None = None,
    chat_id: int | None = None,
    on_chat_model_changed=None,
    on_live_model_changed=None,
    on_clear_history=None,
    on_select_chat=None,
    on_delete_chat=None,
    restore_section=None,
) -> ft.AlertDialog:
    status = ft.Text("Изменения применяются сразу", size=12, color=color("#47747a"), expand=True)

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
            "Профиль и аккаунт",
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
                on_open_memory=lambda: select_page(6),
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
            lambda: build_history_page(chat_list, set_status, chat_id, on_clear_history, page=page, on_select=on_select_chat, on_delete=on_delete_chat),
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
            lambda: build_about_page(page),
        ),
        ("Память обо мне", ft.Icons.PSYCHOLOGY_OUTLINED,
         "Сведения, которые ИИ использует в будущих разговорах",
         lambda: build_memory_page(page, set_status)),
    ]

    page_title = ft.Text("Настройки", size=22, color=color("#123b43"), weight=ft.FontWeight.W_600,
                         max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    try:
        from ..app.theme.motion import switcher
    except ImportError:
        from app.theme.motion import switcher
    page_host=switcher(page,ft.Container());page_host.expand=True
    selected_page = [None]

    def scroll_page(control):
        # AnimatedSwitcher lays children out loosely. Give the scrolling body
        # a finite viewport rather than letting it grow to the page's contents.
        height=getattr(page_host,'height',None) or max(96,min(600,(platforms.available_height(page) or 800)-168))
        return ft.ListView(height=height,spacing=10,scroll=ft.ScrollMode.ALWAYS,
            controls=[apply_palette(control)])

    async def load_personalization(index, generation):
        # Reading model metadata can initialize LiteRT. Do it only in the
        # requested section, without blocking navigation or the Flutter loop.
        try:
            try:
                from ..services import mobile_runtime
            except ImportError:
                from services import mobile_runtime
            await mobile_runtime.refresh_capabilities()
        finally:
            if selected_page[0] == generation:
                page_host.content = scroll_page(sections[index][3]())
                page.update()

    def select_page(index: int):
        generation = object()
        selected_page[0] = generation
        if index == 1 and platforms.is_android():
            page_host.content = ft.Row(controls=[ft.ProgressRing(width=24, height=24),
                                                  ft.Text('Проверяем установленные модели…')])
            page.run_task(load_personalization, index, generation)
        else:
            page_host.content = scroll_page(sections[index][3]())
        page_title.value = sections[index][0]
        back_button.visible = True
        navigation.save(settings=sections[index][0], storage=None)
        page.update()

    def show_home(_=None):
        if page_title.value == 'Память обо мне':
            select_page(1)
            return
        selected_page[0] = None
        page_host.content = scroll_page(home_page)
        page_title.value = "Настройки"
        back_button.visible = False
        navigation.save(settings='home', storage=None)
        page.update()

    home_page = ft.Column(
        spacing=8,
        controls=[
            section_title("Параметры приложения"),
            *[
                build_navigation_button(
                    icon,
                    label,
                    subtitle,
                    lambda _, selected=index: select_page(selected),
                )
                for index, (label, icon, subtitle, _builder) in enumerate(sections) if index != 6
            ],
        ],
    )
    page_host.content = scroll_page(home_page)
    back_button = build_back_button(show_home)

    if start_section is not None:
        select_page(start_section)
    elif restore_section:
        index = next((i for i, section in enumerate(sections) if section[0] == restore_section), None)
        if index is not None:
            select_page(index)
    else:
        navigation.save(settings='home', storage=None)

    def close(_=None):
        selected_page[0] = None
        navigation.clear()
        page.pop_dialog()

    def dismissed(_=None):
        selected_page[0] = None
        navigation.clear()

    mobile_form = compact_layout(getattr(page, 'width', None))
    content = ft.Column(
        width=max(220, min(750, page.width - (24 if mobile_form else 112))) if isinstance(page.width, (int, float)) else 750,
        height=max(220, min(900 if start_section==0 else 600, page.height - (48 if mobile_form else 140))) if isinstance(page.height, (int, float)) else 600,
        spacing=0,
        controls=[
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=18, vertical=16),
                bgcolor=color("#eafffa"),
                border=ft.Border.only(bottom=ft.BorderSide(1,color("#b9eee4"))),
                border_radius=ft.BorderRadius.only(top_left=16, top_right=16),
                content=ft.Column(
                    spacing=6,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                back_button,
                                ft.Column(
                                    expand=True,
                                    spacing=1,
                                    controls=[
                                        ft.Text("Xopilot", size=12, weight=ft.FontWeight.W_500, color=color("#087f8c")),
                                        page_title,
                                    ],
                                ),
                                ft.IconButton(icon=ft.Icons.CLOSE,
                                    tooltip="Закрыть настройки", on_click=close,
                                    icon_color=color("#123b43"),bgcolor=color("#dff8f3"),icon_size=22),
                            ],
                        ),
                        ft.Row(controls=[status]),
                    ],
                ),
            ),
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                expand=True,
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
                bgcolor=color("#eafffa"),
                content=ft.Row(expand=True,vertical_alignment=ft.CrossAxisAlignment.STRETCH,controls=[page_host]),
            ),
        ],
    )


    dialog = ft.AlertDialog(
        modal=False,
        content=content,
        bgcolor=color("#eafffa"),
        shape=ft.RoundedRectangleBorder(radius=28),
        inset_padding=ft.Padding.all(12) if mobile_form else ft.Padding.symmetric(horizontal=32, vertical=20),
        content_padding=ft.Padding.all(0) if mobile_form else None,
        barrier_color=color("#88000000"),
        on_dismiss=dismissed,
    )
    dialog.__dict__['_xopilot_full_width'] = True
    def fit_body():
        page_host.height=max(60,content.height-120)
        if isinstance(page_host.content,ft.ListView):page_host.content.height=page_host.height
    dialog.__dict__['_xopilot_fit_content'] = fit_body
    fit_body()
    return dialog
