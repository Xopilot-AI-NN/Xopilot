"""
Файл: App/app/live_conversation.py
Разработчик: DenBroLiik
Описание: Голосовой режим: слушать реплику, распознать, ответить и озвучить.
    Дополнительно — две кнопки-тумблера (камера/экран): когда один из них включён, перед
    каждым ответом захватывается один кадр и передаётся модели вместе с голосовым вопросом —
    так модель «видит», что происходит в момент реплики.
    UI управляет состояниями и отменой; устройства и модель находятся в services.
"""

import asyncio
import threading
from concurrent.futures import CancelledError

import flet as ft

from .buttons.live import build_live_button
from .buttons.live_camera import build_live_camera_button
from .buttons.live_display import build_live_display_button
try:
    from ..services.live_audio import check_live_audio, record_utterance
    from ..services.speech_output import SpeechOutput
    from ..services.llm import (
        SpeechNotRecognizedError, generate_live_reply, prepare_voice_model, transcribe_audio,
    )
    from ..services.model_settings import get_selected_live_model, model_display_name
    from ..services.live_vision import capture_camera_frame, capture_screen_frame
except ImportError:
    from services.live_audio import check_live_audio, record_utterance
    from services.speech_output import SpeechOutput
    from services.llm import (
        SpeechNotRecognizedError, generate_live_reply, prepare_voice_model, transcribe_audio,
    )
    from services.model_settings import get_selected_live_model, model_display_name
    from services.live_vision import capture_camera_frame, capture_screen_frame


class LiveConversation:
    def __init__(self, page, is_busy, get_history, on_user_message, on_ai_message):
        self.page = page
        self.is_busy = is_busy
        self.get_history = get_history
        self.on_user_message = on_user_message
        self.on_ai_message = on_ai_message
        self.button = build_live_button(on_click=self.toggle)
        self.camera_on = False
        self.screen_on = False
        self.camera_button = build_live_camera_button(on_click=self.toggle_camera)
        self.screen_button = build_live_display_button(on_click=self.toggle_screen)
        self.status_text = ft.Text(size=12, color="#123b43", expand=True)
        self.interrupt_button = ft.TextButton(
            content="Перебить", style=ft.ButtonStyle(color="#087f8c"), on_click=self.interrupt,
        )
        self.end_button = ft.IconButton(
            icon=ft.Icons.CALL_END, icon_color="#d9364f",
            tooltip="Завершить Live", on_click=self.stop,
        )
        self.status = ft.Row(
            controls=[
                self.camera_button, self.screen_button,
                self.status_text, self.interrupt_button, self.end_button,
            ],
            visible=False,
        )
        self._state = "idle"
        self._stopped = threading.Event()
        self._turn_cancelled = threading.Event()
        self._task = None
        self._closed = False
        self._live_model = None
        self._vision_note = ""  # причина, по которой кадр камеры/экрана не получено
        self.refresh_model_label()

    @property
    def busy(self):
        return self._state != "idle"

    def _render(self, message):
        self.status_text.value = message
        self.status.visible = bool(message)
        self.interrupt_button.visible = self._state in {"transcribing", "thinking", "speaking", "interrupting"}
        self.interrupt_button.disabled = self._state == "interrupting"
        self.end_button.icon = ft.Icons.CALL_END if self.busy else ft.Icons.CLOSE
        self.end_button.tooltip = "Завершить Live" if self.busy else "Закрыть"
        self.button.content = ft.Icon(
            ft.Icons.CALL_END if self.busy else ft.Icons.GRAPHIC_EQ,
            color=ft.Colors.WHITE, size=20,
        )
        self.button.bgcolor = "#d9364f" if self.busy else "#ff6666ff"
        self.button.tooltip = (
            "Завершить Live"
            if self.busy
            else f"Live — {model_display_name(get_selected_live_model())}"
        )
        if not self._closed:
            self.page.update()

    def _set_state(self, state, message):
        self._state = state
        self._render(message)

    def refresh_model_label(self, _filename=None):
        if not self.busy:
            self.button.tooltip = f"Live — {model_display_name(get_selected_live_model())}"
            try:
                self.button.update()
            except Exception:
                pass

    def _refresh_vision_buttons(self):
        self.camera_button.border = ft.Border.all(3 if self.camera_on else 2, "#00c753" if self.camera_on else "#ffffff")
        self.camera_button.tooltip = "Live — камера включена" if self.camera_on else "Live — показать с камеры"
        self.screen_button.border = ft.Border.all(3 if self.screen_on else 2, "#00c753" if self.screen_on else "#ffffff")
        self.screen_button.tooltip = "Live — экран включён" if self.screen_on else "Live — трансляция экрана"
        if not self._closed:
            self.camera_button.update()
            self.screen_button.update()

    async def toggle_camera(self, _=None):
        """Вкл/выкл передачи кадра с камеры модели перед каждым ответом. Камера и экран взаимоисключают друг друга —
        на одну реплику передаётся только одно изображение."""
        self.camera_on = not self.camera_on
        if self.camera_on:
            self.screen_on = False
        self._refresh_vision_buttons()

    async def toggle_screen(self, _=None):
        """Вкл/выкл передачи снимка экрана модели перед каждым ответом."""
        self.screen_on = not self.screen_on
        if self.screen_on:
            self.camera_on = False
        self._refresh_vision_buttons()

    async def toggle(self, _=None):
        if self._closed:
            return
        if self.busy:
            await self.stop()
            return
        if self.is_busy():
            self._render("Дождитесь ответа ИИ или завершите диктовку перед запуском Live.")
            return
        if self.page.web:
            self._render("Live доступен в настольном приложении Xopilot.")
            return
        selected_model = get_selected_live_model()
        if not selected_model:
            self._render("Live: нет локальной модели с поддержкой аудио в App/data/models/.")
            return
        self._live_model = selected_model
        self._stopped = threading.Event()
        self._turn_cancelled = threading.Event()
        self._set_state(
            "preparing",
            f"Live · {model_display_name(selected_model)} · Подготавливаю голосовой разговор…",
        )
        self._task = asyncio.create_task(self._run())

    def _check_turn(self):
        if self._turn_cancelled.is_set() or self._stopped.is_set():
            raise CancelledError()

    async def _capture_vision_frame(self):
        """Кадр с камеры/экрана для текущей реплики, если включена соответствующая кнопка.
        Ошибка захвата (камера занята, Wayland без скриншотера и т.п.) не прерывает
        разговор — отвечаем без картинки, но причина показывается в статусе (_vision_note).
        """
        self._vision_note = ""
        if self.camera_on:
            source, message, capture = "Камера", "Live · Смотрю в камеру…", capture_camera_frame
        elif self.screen_on:
            source, message, capture = "Экран", "Live · Смотрю на экран…", capture_screen_frame
        else:
            return None
        self._set_state("thinking", message)
        try:
            return await asyncio.to_thread(capture)
        except Exception as exc:
            self._vision_note = f"{source}: {exc} Ответ был без картинки."
            return None

    async def _run(self):
        error = ""
        try:
            await asyncio.to_thread(check_live_audio)
            speaker = await asyncio.to_thread(SpeechOutput)
            model_filename = self._live_model or get_selected_live_model()
            if not model_filename:
                raise RuntimeError("Не выбрана модель Live.")
            await asyncio.to_thread(prepare_voice_model, self._stopped, model_filename)
            hint = "Говорите — отвечу после паузы."
            while not self._stopped.is_set():
                self._turn_cancelled = threading.Event()
                try:
                    self._set_state("listening", f"Live · Слушаю. {hint}")
                    wav = await asyncio.to_thread(record_utterance, self._turn_cancelled)
                    self._check_turn()
                    self._set_state("transcribing", "Live · Распознаю вашу реплику…")
                    transcript = await asyncio.to_thread(
                        transcribe_audio, wav, self._turn_cancelled, model_filename
                    )
                    self._check_turn()
                    await self.on_user_message(transcript)
                    self._check_turn()
                    image_bytes = await self._capture_vision_frame()
                    self._check_turn()
                    history = self.get_history()
                    self._set_state("thinking", "Live · Готовлю ответ…")
                    reply = await asyncio.to_thread(
                        generate_live_reply, history, self._turn_cancelled, model_filename, image_bytes,
                    )
                    self._check_turn()
                    await self.on_ai_message(reply)
                    self._check_turn()
                    self._set_state("speaking", "Live · Говорю. Можно перебить кнопкой.")
                    await asyncio.to_thread(speaker.speak, reply, self._turn_cancelled)
                    # Дать динамикам закончить звучание перед повторным открытием микрофона.
                    await asyncio.sleep(0.25)
                    hint = self._vision_note or "Говорите — отвечу после паузы."
                except SpeechNotRecognizedError:
                    hint = "Не разобрал речь. Повторите фразу."
                except (CancelledError, asyncio.CancelledError):
                    externally_cancelled = getattr(
                        asyncio.current_task(), "cancelling",
                        lambda: not (self._turn_cancelled.is_set() or self._stopped.is_set()),
                    )()
                    if externally_cancelled:
                        self._stopped.set()
                        self._turn_cancelled.set()
                        raise
                    hint = "Говорите — предыдущий ответ остановлен."
        except (CancelledError, asyncio.CancelledError):
            externally_cancelled = getattr(
                asyncio.current_task(), "cancelling", lambda: not self._stopped.is_set(),
            )()
            self._stopped.set()
            self._turn_cancelled.set()
            if externally_cancelled:
                raise
        except Exception as exc:
            if not self._stopped.is_set():
                error = f"Live: {exc}"
        finally:
            self._set_state("idle", error)

    async def interrupt(self, _=None):
        if self._state not in {"transcribing", "thinking", "speaking"}:
            return
        self._turn_cancelled.set()
        self._set_state("interrupting", "Live · Останавливаю ответ…")

    async def stop(self, _=None):
        if not self.busy:
            self._render("")
            return
        self._stopped.set()
        self._turn_cancelled.set()
        self._set_state("stopping", "Live · Завершаю разговор…")

    async def close(self, _=None):
        self._closed = True
        await self.stop()