"""
Файл: /App/settings/personalizations/main.py
Описание: __Страница персонализации__.
           Тема, язык, активные модели ИИ и голос Live.
"""

from __future__ import annotations

import asyncio

import flet as ft

from ..common import section_title, setting_row
from .buttons.language import build_language_select
from .buttons.theme import build_theme_switch
try:
    from ...services.llm import list_local_models
    from ...services.model_settings import (
        get_selected_chat_model,
        get_selected_live_model,
        list_audio_models,
        model_display_name,
        set_selected_chat_model,
        set_selected_live_model,
    )
    from ...services.voice_catalog import VOICES
    from ...services.voice_settings import get_selected_voice, set_selected_voice
except ImportError:
    from services.llm import list_local_models
    from services.model_settings import (
        get_selected_chat_model,
        get_selected_live_model,
        list_audio_models,
        model_display_name,
        set_selected_chat_model,
        set_selected_live_model,
    )
    from services.voice_catalog import VOICES
    from services.voice_settings import get_selected_voice, set_selected_voice


_TEXT = "#123b43"
_MUTED = "#47747a"
_ERROR = "#b3261e"
_MENU_BG = "#f5fffc"
_MENU_HOVER = "#e3f7f2"
_MENU_FOCUS = "#d7f1eb"
_MENU_BORDER = "#b6e5df"
_MENU_SHADOW = "#33000000"


def _border() -> dict[ft.ControlState, ft.InputBorder]:
    return {
        ft.ControlState.DEFAULT: ft.OutlineInputBorder(
            border_radius=12,
            side=ft.BorderSide(color="#a8ddd7"),
        ),
        ft.ControlState.FOCUSED: ft.OutlineInputBorder(
            border_radius=12,
            side=ft.BorderSide(width=2, color="#087f8c"),
        ),
    }


def _menu_style() -> ft.MenuStyle:
    return ft.MenuStyle(
        bgcolor=_MENU_BG,
        elevation=10,
        shadow_color=_MENU_SHADOW,
        shape=ft.RoundedRectangleBorder(radius=14),
        side=ft.BorderSide(color=_MENU_BORDER, width=1),
        padding=ft.Padding.all(6),
    )


def _option_style() -> ft.ButtonStyle:
    return ft.ButtonStyle(
        color=_TEXT,
        bgcolor={
            ft.ControlState.DEFAULT: _MENU_BG,
            ft.ControlState.HOVERED: _MENU_HOVER,
            ft.ControlState.FOCUSED: _MENU_FOCUS,
        },
        overlay_color=ft.Colors.TRANSPARENT,
        shape=ft.RoundedRectangleBorder(radius=10),
        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
        animation_duration=120,
    )


def _option(key: str, text: str, icon) -> ft.DropdownOption:
    return ft.DropdownOption(
        key=key,
        text=text,
        leading_icon=icon,
        style=_option_style(),
    )


def _dropdown(label: str, value, options, icon, hint: str) -> ft.Dropdown:
    # Не задаём огромную фиксированную высоту popup. Для 1-4 вариантов меню
    # занимает ровно нужное место; при большем количестве ограничиваем высоту,
    # после чего сам Dropdown становится прокручиваемым.
    option_count = len(options)
    menu_height = min(224, 12 + max(1, option_count) * 44)

    return ft.Dropdown(
        label=label,
        value=value,
        disabled=not options,
        hint_text=hint if not options else None,
        options=options,
        leading_icon=icon,
        trailing_icon=ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED,
        selected_trailing_icon=ft.Icons.KEYBOARD_ARROW_UP_ROUNDED,
        filled=True,
        fill_color="#f5fffc",
        bgcolor="#f5fffc",
        hover_color="#edfbf8",
        color=_TEXT,
        text_size=13,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        border=_border(),
        menu_style=_menu_style(),
        menu_height=menu_height,
        expanded_insets=ft.Padding.only(top=4),
        expand=True,
    )


def _preference_card(icon, title: str, description: str, control, feedback: ft.Text) -> ft.Container:
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        border_radius=14,
        bgcolor="#dff8f3",
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    spacing=10,
                    controls=[
                        ft.Container(
                            width=36,
                            height=36,
                            border_radius=18,
                            bgcolor="#c9f1e9",
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(icon, size=19, color="#087f8c"),
                        ),
                        ft.Column(
                            expand=True,
                            spacing=2,
                            controls=[
                                ft.Text(title, size=14, color=_TEXT, weight=ft.FontWeight.W_600),
                                ft.Text(description, size=11, color=_MUTED),
                            ],
                        ),
                    ],
                ),
                control,
                feedback,
            ],
        ),
    )


def build_personalizations_page(
    page: ft.Page,
    on_status,
    on_chat_model_changed=None,
    on_live_model_changed=None,
) -> ft.Column:
    models = list_local_models()
    live_models = list_audio_models()
    installed_voices = {
        voice_id: profile for voice_id, profile in VOICES.items() if profile.installed
    }

    chat_saved = get_selected_chat_model()
    live_saved = get_selected_live_model()
    voice_saved = get_selected_voice()
    if voice_saved not in installed_voices:
        voice_saved = None

    chat_feedback = ft.Text(
        "Быстро переключить эту же модель можно кнопкой-роботом в строке ввода.",
        size=10,
        color=_MUTED,
    )
    live_feedback = ft.Text(
        "Для Live показываются только LiteRT-LM модели с поддержкой аудиовхода.",
        size=10,
        color=_MUTED,
    )
    voice_feedback = ft.Text(
        "Голос используется для озвучивания ответов Live.",
        size=10,
        color=_MUTED,
    )

    chat_select = _dropdown(
        "Модель чата",
        chat_saved,
        [_option(name, model_display_name(name), ft.Icons.SMART_TOY_OUTLINED) for name in models],
        ft.Icons.SMART_TOY_OUTLINED,
        "Сначала установите модель в разделе «Модели»",
    )
    live_select = _dropdown(
        "Модель Live",
        live_saved,
        [_option(name, model_display_name(name), ft.Icons.GRAPHIC_EQ) for name in live_models],
        ft.Icons.GRAPHIC_EQ,
        "Нет установленной модели с поддержкой аудио",
    )
    voice_select = _dropdown(
        "Голос Live",
        voice_saved,
        [
            _option(
                voice_id,
                f"{profile.name} — {profile.gender} · {profile.description}",
                ft.Icons.RECORD_VOICE_OVER,
            )
            for voice_id, profile in installed_voices.items()
        ],
        ft.Icons.RECORD_VOICE_OVER,
        "Сначала установите голос в разделе «Модели»",
    )

    async def change_chat(_):
        requested = chat_select.value
        if not requested:
            return
        chat_select.disabled = True
        page.update()
        try:
            persisted = await asyncio.to_thread(set_selected_chat_model, requested)
        except Exception as exc:
            chat_select.value = get_selected_chat_model()
            chat_feedback.value = str(exc)
            chat_feedback.color = _ERROR
            on_status("Модель чата не изменена")
        else:
            chat_feedback.value = (
                f"{model_display_name(requested)} · будет загружена при следующем ответе."
                + ("" if persisted else " Только на эту сессию.")
            )
            chat_feedback.color = _MUTED
            on_status(f"Чат · {model_display_name(requested)}")
            if on_chat_model_changed is not None:
                on_chat_model_changed(requested)
        finally:
            chat_select.disabled = not models
            page.update()

    async def change_live(_):
        requested = live_select.value
        if not requested:
            return
        live_select.disabled = True
        page.update()
        try:
            persisted = await asyncio.to_thread(set_selected_live_model, requested)
        except Exception as exc:
            live_select.value = get_selected_live_model()
            live_feedback.value = str(exc)
            live_feedback.color = _ERROR
            on_status("Модель Live не изменена")
        else:
            live_feedback.value = (
                f"{model_display_name(requested)} · применится со следующего запуска Live."
                + ("" if persisted else " Только на эту сессию.")
            )
            live_feedback.color = _MUTED
            on_status(f"Live · {model_display_name(requested)}")
            if on_live_model_changed is not None:
                on_live_model_changed(requested)
        finally:
            live_select.disabled = not live_models
            page.update()

    async def change_voice(_):
        requested = voice_select.value
        if not requested:
            return
        voice_select.disabled = True
        page.update()
        try:
            await asyncio.to_thread(set_selected_voice, requested)
        except Exception as exc:
            current = get_selected_voice()
            voice_select.value = current if current in installed_voices else None
            voice_feedback.value = str(exc)
            voice_feedback.color = _ERROR
            on_status("Голос Live не изменён")
        else:
            profile = VOICES[requested]
            voice_feedback.value = f"{profile.name} · применится со следующего ответа Live."
            voice_feedback.color = _MUTED
            on_status(f"Голос · {profile.name}")
        finally:
            voice_select.disabled = not installed_voices
            page.update()

    chat_select.on_select = change_chat
    live_select.on_select = change_live
    voice_select.on_select = change_voice

    return ft.Column(
        spacing=8,
        controls=[
            section_title("Внешний вид"),
            setting_row(
                ft.Icons.DARK_MODE_OUTLINED,
                "Тёмная тема",
                "Переключить оформление приложения",
                build_theme_switch(page, on_status),
            ),
            setting_row(
                ft.Icons.LANGUAGE,
                "Язык интерфейса",
                "Выберите язык меню и сообщений",
                build_language_select(on_status),
            ),
            section_title("ИИ и Live"),
            _preference_card(
                ft.Icons.SMART_TOY_OUTLINED,
                "Модель чата",
                "Основная модель для обычных сообщений.",
                chat_select,
                chat_feedback,
            ),
            _preference_card(
                ft.Icons.GRAPHIC_EQ,
                "Модель Live",
                "Модель для распознавания речи и генерации ответа в Live.",
                live_select,
                live_feedback,
            ),
            _preference_card(
                ft.Icons.RECORD_VOICE_OVER,
                "Голос Live",
                "Тембр, которым Xopilot озвучивает ответы.",
                voice_select,
                voice_feedback,
            ),
        ],
    )
