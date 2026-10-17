"""
Файл: App/settings/models/main.py
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: Загрузка локальной Gemma 4 E2B и Piper-моделей голосов Live.

Выбор активной модели и голоса находится в «Персонализация».
"""

from __future__ import annotations

import asyncio
import threading
import time
from concurrent.futures import CancelledError

import flet as ft
try:
    from ...app.theme.palette import color
except ImportError:
    from app.theme.palette import color

from ..common import section_title
try:
    from ...app.models.model_download import ModelDownloadPanel
    from ...app.menu.buttons.brand import style_brand_button
except ImportError:
    from app.models.model_download import ModelDownloadPanel
    from app.menu.buttons.brand import style_brand_button
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
                style_brand_button(ft.Container(
                    width=42,
                    height=42,
                    border_radius=21,
                    bgcolor=color("#c9f1e9"),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, size=22, color=_ACCENT),
                ), 'ai'),
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
    cancelled=threading.Event()
    def request_cancel(_):
        cancelled.set()
        for state in voice_progress.values():
            state['cancel'].disabled=True
            state['cancel'].content='Отменяю…'
        page.update()
    voice_progress={identifier:{
        'bar':ft.ProgressBar(value=None,visible=False,color=color('#087f8c'),height=4,border_radius=2),
        'label':ft.Text('',size=11,color=_MUTED,visible=False,max_lines=2,overflow=ft.TextOverflow.ELLIPSIS),
        'cancel':ft.TextButton(content='Отменить загрузку',visible=False,on_click=request_cancel),
        'feedback':ft.Text('',size=11,color=_MUTED,visible=False),
    } for identifier in VOICES}

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
        for button in voice_buttons.values():
            button.disabled = value
        if not value:
            for catalogue, buttons in ((VOICES, voice_buttons),):
                for identifier, button in buttons.items():
                    installed = catalogue[identifier].installed
                    button.content = "Переустановить" if installed else "Скачать"
                    status = _status_chip("Установлено" if installed else "Не установлено", installed)
                    button._xopilot_status_chip.bgcolor = status.bgcolor
                    button._xopilot_status_chip.content = status.content
        page.update()

    def make_voice_installer(voice_id: str):
        state=voice_progress[voice_id]
        progress,progress_label,cancel,feedback=(state[key] for key in ('bar','label','cancel','feedback'))
        async def handle(_):
            if busy:
                return
            profile = VOICES[voice_id]
            feedback.visible=True
            cancelled.clear()
            cancel.disabled=False;cancel.content='Отменить загрузку'
            set_busy(True)
            voice_buttons[voice_id].content = "Загрузка…"
            feedback.value = f"Скачиваю модели голоса {profile.name} (ru + en)…"
            feedback.color = color('#47747a')
            on_status(f"Загрузка {profile.name}…")
            progress.visible=progress_label.visible=cancel.visible=True
            progress.value=None;progress_label.value='Подготовка загрузки…'
            page.update()
            try:
                async def show_progress(message):
                    if not busy:return
                    feedback.value = message
                    progress.value=None
                    progress_label.value='Подготовка · ожидайте завершения этапа'
                    page.update()
                last_update=0.0
                loop=asyncio.get_running_loop()
                def download_update(event):
                    nonlocal last_update
                    now=time.monotonic()
                    if event.phase=='download' and event.downloaded and now-last_update<.15:return
                    last_update=now
                    def render():
                        if not busy:return
                        progress.value=(min(1,max(0,event.downloaded/event.total)) if event.total else None) if event.phase=='download' else (1 if event.phase in {'ready','cached'} else None)
                        size=f'{event.downloaded/1048576:.1f} МБ'
                        if event.total:size+=f' из {event.total/1048576:.1f} МБ · {min(100,event.downloaded*100/event.total):.0f}%'
                        progress_label.value=event.name+' · '+('Проверка SHA-256…' if event.phase=='verify' else 'Уже загружено' if event.phase=='cached' else size)
                        page.update()
                    loop.call_soon_threadsafe(render)
                await asyncio.to_thread(install_voice, voice_id,
                                        lambda message: page.run_task(show_progress, message),
                                        on_download=download_update,cancelled=cancelled)
            except (CancelledError,asyncio.CancelledError):
                if not cancelled.is_set():
                    cancelled.set()
                    raise
                feedback.value='Установка отменена. Проверенные файлы сохранены; можно повторить загрузку.'
                feedback.color=color('#47747a')
                on_status('Загрузка отменена')
            except Exception as exc:
                feedback.value = f"Не удалось установить {profile.name}: {exc}"
                feedback.color = color('#c94b4b')
                on_status("Ошибка загрузки голоса")
            else:
                feedback.value = f"Голос {profile.name} установлен. Его можно выбрать в Персонализации."
                feedback.color = color('#47747a')
                voice_buttons[voice_id].content = "Переустановить"
                on_status(f"{profile.name} установлен")
                if on_models_changed is not None:
                    on_models_changed()
            finally:
                progress.visible=progress_label.visible=cancel.visible=False
                set_busy(False)

        return handle

    for voice_id, button in voice_buttons.items():
        button.on_click = make_voice_installer(voice_id)

    model_cards = [_install_card(ft.Icons.SMART_TOY_OUTLINED, model.name, model.description,
                    f'{model.size_label} · Hugging Face · SHA-256 проверяется после загрузки',
                    model.installed, ModelDownloadPanel(model, on_models_changed)) for model in DOWNLOADABLE_MODELS.values()]
    async def import_file(_):
        if busy:return
        try:
            from ...app.materials.file_selection import pick_materials
            from ...services.model_installer import import_model
        except ImportError:
            from app.materials.file_selection import pick_materials
            from services.model_installer import import_model
        import_button.disabled=True;feedback.value='Выберите .litertlm файл. Проверка большой модели может занять некоторое время.';page.update()
        try:
            imported=await pick_materials(page,ft.FilePicker(),store=import_model)
            if imported:
                feedback.value='Модель импортирована, SHA-256 подтверждён'
                if on_models_changed:on_models_changed()
        except Exception as exc:feedback.value=str(exc)
        finally:import_button.disabled=False;page.update()
    import_button=ft.OutlinedButton(content='Импортировать модель из файла',icon=ft.Icons.FILE_OPEN_OUTLINED,on_click=import_file)
    try:
        from ...app.settings.api_settings import open_api_settings
    except ImportError:
        from app.settings.api_settings import open_api_settings

    voice_cards = [
        ft.Column(spacing=6,controls=[_install_card(
            ft.Icons.RECORD_VOICE_OVER,
            profile.name,
            f"{profile.gender} · {profile.description}",
            ("Piper + RVC ONNX · русский + английский · ≈ 980 МБ моделей · первая подготовка автоматически загрузит дополнительные компоненты"
             if profile.id == "miku" else "Piper ONNX · русский + английский · полностью локальная озвучка"),
            profile.installed,
            voice_buttons[voice_id],
        ),*voice_progress[voice_id].values()])
        for voice_id, profile in VOICES.items()
    ]
    try:
        from ...services.platforms import is_android
    except ImportError:
        from services.platforms import is_android
    if is_android():
        from ..voice.android import build_android_voice_controls
        voice_cards = [build_android_voice_controls(page, on_status)]

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
            import_button,
            ft.OutlinedButton(content='API · настроить подключение', icon=ft.Icons.API,
                on_click=lambda _: open_api_settings(page, on_saved=on_models_changed)),
            section_title("Голоса Live"),
            *voice_cards,
            feedback,
        ],
    )
