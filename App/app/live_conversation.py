"""
Файл: App/app/live_conversation.py
Разработчик: DenBroLiik
Описание: Голосовой режим: слушать реплику, распознать, ответить и озвучить.
    UI управляет состояниями и отменой; устройства и модель находятся в services.
"""

import asyncio
import threading
from concurrent.futures import CancelledError

import flet as ft

from .buttons.live import build_live_button
try:
    from ..services.live_audio import check_live_audio, record_utterance
    from ..services.speech_output import SpeechOutput
    from ..services.llm import (
        SpeechNotRecognizedError, generate_live_reply, prepare_voice_model, transcribe_audio,
    )
except ImportError:
    from services.live_audio import check_live_audio, record_utterance
    from services.speech_output import SpeechOutput
    from services.llm import (
        SpeechNotRecognizedError, generate_live_reply, prepare_voice_model, transcribe_audio,
    )


class LiveConversation:
    def __init__(self, page, is_busy, get_history, on_user_message, on_ai_message):
        self.page = page
        self.is_busy = is_busy
        self.get_history = get_history
        self.on_user_message = on_user_message
        self.on_ai_message = on_ai_message
        self.button = build_live_button(on_click=self.toggle)
        self.status_text = ft.Text(size=12, color="#123b43", expand=True)
        self.interrupt_button = ft.TextButton(
            "Перебить", style=ft.ButtonStyle(color="#087f8c"), on_click=self.interrupt,
        )
        self.end_button = ft.IconButton(
            icon=ft.Icons.CALL_END, icon_color="#d9364f",
            tooltip="Завершить Live", on_click=self.stop,
        )
        self.status = ft.Row(
            controls=[self.status_text, self.interrupt_button, self.end_button],
            visible=False,
        )
        self._state = "idle"
        self._stopped = threading.Event()
        self._turn_cancelled = threading.Event()
        self._task = None
        self._closed = False

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
        self.button.tooltip = "Завершить Live" if self.busy else "Live — голосовой разговор"
        if not self._closed:
            self.page.update()

    def _set_state(self, state, message):
        self._state = state
        self._render(message)

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
        self._stopped = threading.Event()
        self._turn_cancelled = threading.Event()
        self._set_state("preparing", "Live · Подготавливаю голосовой разговор…")
        self._task = asyncio.create_task(self._run())

    def _check_turn(self):
        if self._turn_cancelled.is_set() or self._stopped.is_set():
            raise CancelledError()

    async def _run(self):
        error = ""
        try:
            await asyncio.to_thread(check_live_audio)
            speaker = await asyncio.to_thread(SpeechOutput)
            await asyncio.to_thread(prepare_voice_model, self._stopped)
            hint = "Говорите — отвечу после паузы."
            while not self._stopped.is_set():
                self._turn_cancelled = threading.Event()
                try:
                    self._set_state("listening", f"Live · Слушаю. {hint}")
                    wav = await asyncio.to_thread(record_utterance, self._turn_cancelled)
                    self._check_turn()
                    self._set_state("transcribing", "Live · Распознаю вашу реплику…")
                    transcript = await asyncio.to_thread(transcribe_audio, wav, self._turn_cancelled)
                    self._check_turn()
                    await self.on_user_message(transcript)
                    self._check_turn()
                    history = self.get_history()
                    self._set_state("thinking", "Live · Готовлю ответ…")
                    reply = await asyncio.to_thread(generate_live_reply, history, self._turn_cancelled)
                    self._check_turn()
                    await self.on_ai_message(reply)
                    self._check_turn()
                    self._set_state("speaking", "Live · Говорю. Можно перебить кнопкой.")
                    await asyncio.to_thread(speaker.speak, reply, self._turn_cancelled)
                    # Дать динамикам закончить звучание перед повторным открытием микрофона.
                    await asyncio.sleep(0.25)
                    hint = "Говорите — отвечу после паузы."
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
