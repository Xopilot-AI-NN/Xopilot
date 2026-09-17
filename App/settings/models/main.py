"""
Файл: App/settings/models/main.py
Описание: Загрузка локальной Gemma 4 E2B и Piper-моделей голосов Live.

Выбор активной модели и голоса находится в «Персонализация».
"""

from __future__ import annotations

import asyncio

import flet as ft

from ..common import section_title
try:
    from ...services.model_installer import GEMMA_4_E2B, install_model
    from ...services.voice_catalog import VOICES
    from ...services.voice_installer import install_voice
except ImportError:
    from services.model_installer import GEMMA_4_E2B, install_model
    from services.voice_catalog import VOICES
    from services.voice_installer import install_voice


_TEXT = "#123b43"
_MUTED = "#47747a"
_ACCENT = "#087f8c"
_ERROR = "#b3261e"


def _status_chip(text: str, installed: bool) -> ft.Container:
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=9, vertical=4),
        border_radius=12,
        bgcolor="#d8f5e7" if installed else "#fff0d8",
        content=ft.Text(
            text,
            size=10,
            color="#08734d" if installed else "#8a5a00",
            weight=ft.FontWeight.W_600,
        ),
    )


def _install_card(icon, title: str, subtitle: str, details: str, installed: bool, button) -> ft.Container:
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        border_radius=14,
        bgcolor="#dff8f3",
        content=ft.Row(
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=42,
                    height=42,
                    border_radius=21,
                    bgcolor="#c9f1e9",
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, size=22, color=_ACCENT),
                ),
                ft.Column(
                    expand=True,
                    spacing=3,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Text(title, size=14, color=_TEXT, weight=ft.FontWeight.W_600),
                                _status_chip("Установлено" if installed else "Не установлено", installed),
                            ],
                        ),
                        ft.Text(subtitle, size=11, color=_MUTED, max_lines=2),
                        ft.Text(details, size=10, color="#6a8d91", max_lines=2),
                    ],
                ),
                button,
            ],
        ),
    )


def build_models_page(page, on_status, on_models_changed=None):
    feedback = ft.Text(
        "Загрузки сохраняются локально в App/data/models.",
        size=11,
        color=_MUTED,
    )
    busy = False

    gemma_button = ft.FilledButton(
        content="Переустановить" if GEMMA_4_E2B.installed else "Скачать",
        icon=ft.Icons.DOWNLOAD,
    )

    voice_buttons: dict[str, ft.FilledButton] = {
        voice_id: ft.FilledButton(
            content="Переустановить" if profile.installed else "Скачать",
            icon=ft.Icons.DOWNLOAD,
        )
        for voice_id, profile in VOICES.items()
    }

    def set_busy(value: bool):
        nonlocal busy
        busy = value
        gemma_button.disabled = value
        for button in voice_buttons.values():
            button.disabled = value
        page.update()

    async def install_gemma(_):
        if busy:
            return
        set_busy(True)
        feedback.value = f"Скачиваю {GEMMA_4_E2B.name} ({GEMMA_4_E2B.size_label})…"
        feedback.color = _MUTED
        on_status("Загрузка модели…")
        page.update()
        try:
            path = await asyncio.to_thread(install_model, GEMMA_4_E2B.id)
        except Exception as exc:
            feedback.value = f"Не удалось скачать {GEMMA_4_E2B.name}: {exc}"
            feedback.color = _ERROR
            on_status("Ошибка загрузки модели")
        else:
            feedback.value = f"{GEMMA_4_E2B.name} установлена: {path.name}"
            feedback.color = _MUTED
            gemma_button.content = "Переустановить"
            on_status(f"{GEMMA_4_E2B.name} установлена")
            if on_models_changed is not None:
                on_models_changed()
        finally:
            set_busy(False)

    gemma_button.on_click = install_gemma

    def make_voice_installer(voice_id: str):
        async def handle(_):
            if busy:
                return
            profile = VOICES[voice_id]
            set_busy(True)
            feedback.value = f"Скачиваю модели голоса {profile.name} (ru + en)…"
            feedback.color = _MUTED
            on_status(f"Загрузка {profile.name}…")
            page.update()
            try:
                await asyncio.to_thread(install_voice, voice_id)
            except Exception as exc:
                feedback.value = f"Не удалось установить {profile.name}: {exc}"
                feedback.color = _ERROR
                on_status("Ошибка загрузки голоса")
            else:
                feedback.value = f"Голос {profile.name} установлен. Его можно выбрать в Персонализации."
                feedback.color = _MUTED
                voice_buttons[voice_id].content = "Переустановить"
                on_status(f"{profile.name} установлен")
                if on_models_changed is not None:
                    on_models_changed()
            finally:
                set_busy(False)

        return handle

    for voice_id, button in voice_buttons.items():
        button.on_click = make_voice_installer(voice_id)

    gemma_card = _install_card(
        ft.Icons.SMART_TOY_OUTLINED,
        GEMMA_4_E2B.name,
        GEMMA_4_E2B.description,
        f"{GEMMA_4_E2B.size_label} · Hugging Face · SHA-256 проверяется после загрузки",
        GEMMA_4_E2B.installed,
        gemma_button,
    )

    voice_cards = [
        _install_card(
            ft.Icons.RECORD_VOICE_OVER,
            profile.name,
            f"{profile.gender} · {profile.description}",
            "Piper ONNX · русский + английский · тот же установщик, что scripts/install_russian_voice.py",
            profile.installed,
            voice_buttons[voice_id],
        )
        for voice_id, profile in VOICES.items()
    ]

    return ft.Column(
        spacing=10,
        controls=[
            section_title("Модели"),
            ft.Text("Загрузка моделей", size=18, color=_TEXT, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Здесь устанавливаются файлы моделей. Какая модель и какой голос активны, "
                "настраивается в разделе «Персонализация».",
                size=12,
                color=_MUTED,
            ),
            section_title("ИИ"),
            gemma_card,
            section_title("Голоса Live"),
            *voice_cards,
            feedback,
        ],
    )
