"""
Файл: App/settings/models/main.py
Описание: Загрузка локальной Gemma 4 E2B и Piper-моделей голосов Live.

Выбор активной модели и голоса находится в «Персонализация».
"""

from __future__ import annotations

import asyncio

import flet as ft
try:
    from ...app.palette import color
except ImportError:
    from app.palette import color

from ..common import section_title
try:
    from ...services.model_installer import GEMMA_4_E2B, DOWNLOADABLE_MODELS, install_model, MODELS_DIR
    from ...services.voice_catalog import VOICES
    from ...services.voice_installer import install_voice
except ImportError:
    from services.model_installer import GEMMA_4_E2B, DOWNLOADABLE_MODELS, install_model, MODELS_DIR
    from services.voice_catalog import VOICES
    from services.voice_installer import install_voice


_TEXT = color("#123b43")
_MUTED = color("#47747a")
_ACCENT = color("#087f8c")
_ERROR = color("#b3261e")


def _status_chip(text: str, installed: bool) -> ft.Container:
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=9, vertical=4),
        border_radius=12,
        bgcolor=color("#d8f5e7") if installed else color("#fff0d8"),
        content=ft.Text(
            text,
            size=10,
            color=color("#08734d") if installed else color("#8a5a00"),
            weight=ft.FontWeight.W_600,
        ),
    )


def _install_card(icon, title: str, subtitle: str, details: str, installed: bool, button) -> ft.Container:
    status = _status_chip("Установлено" if installed else "Не установлено", installed)
    button._xopilot_status_chip = status
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        border_radius=14,
        bgcolor=color("#dff8f3"),
        content=ft.Column(
            spacing=10,
            controls=[ft.Row(spacing=12, controls=[
                ft.Container(
                    width=42,
                    height=42,
                    border_radius=21,
                    bgcolor=color("#c9f1e9"),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, size=22, color=_ACCENT),
                ),
                ft.Column(
                    expand=True,
                    spacing=3,
                    controls=[
                        ft.Row(
                            wrap=True,
                            spacing=8,
                            controls=[
                                ft.Text(title, size=14, color=_TEXT, weight=ft.FontWeight.W_600),
                                status,
                            ],
                        ),
                        ft.Text(subtitle, size=11, color=_MUTED, max_lines=2),
                        ft.Text(details, size=10, color=color("#6a8d91"), max_lines=2),
                    ],
                ),
            ]), button],
        ),
    )


def build_models_page(page, on_status, on_models_changed=None):
    feedback = ft.Text(
        f"Загрузки сохраняются локально: {MODELS_DIR}",
        size=11,
        color=_MUTED,
    )
    busy = False

    model_buttons = {key: ft.FilledButton(content='Переустановить' if model.installed else 'Скачать',
                         icon=ft.Icons.DOWNLOAD) for key, model in DOWNLOADABLE_MODELS.items()}

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
        for button in model_buttons.values():
            button.disabled = value
        for button in voice_buttons.values():
            button.disabled = value
        if not value:
            for catalogue, buttons in ((DOWNLOADABLE_MODELS, model_buttons), (VOICES, voice_buttons)):
                for identifier, button in buttons.items():
                    installed = catalogue[identifier].installed
                    button.content = "Переустановить" if installed else "Скачать"
                    status = _status_chip("Установлено" if installed else "Не установлено", installed)
                    button._xopilot_status_chip.bgcolor = status.bgcolor
                    button._xopilot_status_chip.content = status.content
        page.update()

    async def install_gemma(model):
        if busy:
            return
        set_busy(True)
        model_buttons[model.id].content = "Загрузка…"
        feedback.value = f"Скачиваю {model.name} ({model.size_label})…"
        feedback.color = _MUTED
        on_status("Загрузка модели…")
        page.update()
        try:
            path = await asyncio.to_thread(install_model, model.id)
        except Exception as exc:
            feedback.value = f"Не удалось скачать {model.name}: {exc}"
            feedback.color = _ERROR
            on_status("Ошибка загрузки модели")
        else:
            feedback.value = f"{model.name} установлена: {path.name}"
            feedback.color = _MUTED
            model_buttons[model.id].content = "Переустановить"
            on_status(f"{model.name} установлена")
            if on_models_changed is not None:
                on_models_changed()
        finally:
            set_busy(False)

    def installer(model):
        async def handle(_):
            await install_gemma(model)
        return handle
    for key, button in model_buttons.items():
        button.on_click = installer(DOWNLOADABLE_MODELS[key])

    def make_voice_installer(voice_id: str):
        async def handle(_):
            if busy:
                return
            profile = VOICES[voice_id]
            set_busy(True)
            voice_buttons[voice_id].content = "Загрузка…"
            feedback.value = f"Скачиваю модели голоса {profile.name} (ru + en)…"
            feedback.color = _MUTED
            on_status(f"Загрузка {profile.name}…")
            page.update()
            try:
                async def show_progress(message):
                    feedback.value = message
                    page.update()

                await asyncio.to_thread(install_voice, voice_id,
                                        lambda message: page.run_task(show_progress, message))
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

    model_cards = [_install_card(ft.Icons.SMART_TOY_OUTLINED, model.name, model.description,
                    f'{model.size_label} · Hugging Face · SHA-256 проверяется после загрузки',
                    model.installed, model_buttons[model.id]) for model in DOWNLOADABLE_MODELS.values()]
    try:
        from ...app.api_settings import open_api_settings
    except ImportError:
        from app.api_settings import open_api_settings

    voice_cards = [
        _install_card(
            ft.Icons.RECORD_VOICE_OVER,
            profile.name,
            f"{profile.gender} · {profile.description}",
            ("Piper + RVC ONNX · русский + английский · ≈ 980 МБ моделей · первый экспорт занимает несколько минут"
             if profile.id == "miku" else "Piper ONNX · русский + английский · полностью локальная озвучка"),
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
            ft.Text('Zephyr Micro · в разработке', color=_MUTED),
            *model_cards,
            ft.OutlinedButton(content='API · настроить подключение', icon=ft.Icons.API,
                on_click=lambda _: open_api_settings(page, on_saved=on_models_changed)),
            section_title("Голоса Live"),
            *voice_cards,
            feedback,
        ],
    )
