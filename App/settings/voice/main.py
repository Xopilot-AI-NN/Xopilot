"""
Файл: App/settings/voice/main.py
Разработчик: DenBroLiik
Описание: Выбор сохраняемого голоса Live: COVE, Miku или Maple, русский и английский.
"""

import asyncio
import flet as ft

from ..common import section_title
try:
    from ...services.voice_catalog import VOICES
    from ...services.voice_settings import get_selected_voice, set_selected_voice
except ImportError:
    from services.voice_catalog import VOICES
    from services.voice_settings import get_selected_voice, set_selected_voice


def build_voice_page(page, on_status):
    saved = get_selected_voice() or "cove"
    if saved not in VOICES:
        saved = "cove"
    hint = "Выбор сохранится и применится со следующего ответа Live."
    feedback = ft.Text(hint, size=12, color="#47747a")
    select = ft.RadioGroup(
        value=saved,
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Container(
                    padding=ft.padding.Padding.symmetric(horizontal=14, vertical=10),
                    border_radius=12,
                    bgcolor="#dff8f3",
                    content=ft.Column(
                        spacing=1,
                        controls=[
                            ft.Radio(
                                value=profile.id,
                                label=f"{profile.name} — {profile.gender} · ru, en",
                                active_color="#087f8c",
                                label_style=ft.TextStyle(size=15, color="#123b43", weight=ft.FontWeight.W_600),
                            ),
                            ft.Container(
                                padding=ft.padding.Padding.only(left=48, bottom=4),
                                content=ft.Text(profile.description, size=12, color="#47747a"),
                            ),
                        ],
                    ),
                )
                for profile in VOICES.values()
            ],
        ),
    )

    async def change(_):
        nonlocal saved
        if select.disabled:
            return
        requested = select.value
        select.disabled = True
        page.update()
        try:
            await asyncio.to_thread(set_selected_voice, requested)
        except Exception as exc:
            select.value = saved
            feedback.value = str(exc)
            feedback.color = "#b3261e"
            on_status("Голос не изменён")
        else:
            saved = requested if requested in VOICES else "cove"
            feedback.value = hint
            feedback.color = "#47747a"
            on_status(f"{VOICES[saved].name} · Со следующего ответа Live")
        finally:
            select.value = saved
            select.disabled = False
            page.update()

    select.on_change = change
    return ft.Column(
        spacing=12,
        controls=[
            section_title("Голос Live"),
            ft.Text("Выберите голос для ответов ИИ", size=18, color="#123b43", weight=ft.FontWeight.BOLD),
            ft.Text(
                "Все голоса поддерживают русский и английский. Язык озвучки определяется по тексту ответа.",
                size=13, color="#47747a",
            ),
            select,
            feedback,
        ],
    )
