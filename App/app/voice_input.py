"""
Файл: App/app/voice_input.py
Разработчик: DenBroLiik
Описание: Состояния кнопки диктовки, таймер, отмена и добавление речи в черновик.
"""

import asyncio
import threading
from concurrent.futures import CancelledError

import flet as ft

from .buttons.microphone import build_microphone_button
try:
    from ..services.microphone import MAX_RECORDING_SECONDS, MicrophoneRecorder
    from ..services.llm import transcribe_audio
except ImportError:
    from services.microphone import MAX_RECORDING_SECONDS, MicrophoneRecorder
    from services.llm import transcribe_audio


class VoiceInput:
    def __init__(self, page, prompt, is_sending):
        self.page = page
        self.prompt = prompt
        self.is_sending = is_sending
        self.button = build_microphone_button(on_click=self.toggle)
        self.status_text = ft.Text(size=12, color="#123b43", expand=True)
        self.cancel_button = ft.IconButton(
            icon=ft.Icons.CLOSE,
            icon_size=18,
            icon_color="#087f8c",
            tooltip="Отменить диктовку",
            on_click=self.cancel,
        )
        self.status = ft.Row(
            controls=[self.status_text, self.cancel_button],
            visible=False,
        )
        self._recorder = None
        self._task = None
        self._cancelled = threading.Event()
        self._stop_requested = asyncio.Event()
        self._state = "idle"
        self._closed = False

    @property
    def busy(self):
        return self._state != "idle"

    def _render(self, message=""):
        recording = self._state == "recording"
        self.button.content = ft.Icon(
            ft.Icons.STOP if recording else ft.Icons.MIC,
            color=ft.Colors.WHITE,
            size=20,
        )
        self.button.bgcolor = "#d9364f" if recording else "#ff6666ff"
        self.button.tooltip = "Остановить и распознать речь" if recording else "Диктовка"
        self.button.disabled = self.busy and not recording
        self.status_text.value = message
        self.status.visible = bool(message)
        self.cancel_button.tooltip = "Отменить диктовку" if self.busy else "Закрыть"
        if not self._closed:
            self.page.update()

    async def toggle(self, _=None):
        if self._closed:
            return
        if self._state == "recording":
            self._stop_requested.set()
            self._state = "processing"
            self._render("Распознаю речь…")
            return
        if self.busy:
            return
        if self.is_sending():
            self._render("Завершите Live или дождитесь ответа ИИ, затем включите диктовку.")
            return
        if self.page.web:
            self._render("Диктовка доступна в настольном приложении Xopilot.")
            return
        self._cancelled = threading.Event()
        self._stop_requested = asyncio.Event()
        self._recorder = MicrophoneRecorder()
        self._state = "starting"
        self._render("Включаю микрофон…")
        self._task = asyncio.create_task(self._record_and_transcribe())

    async def _record_and_transcribe(self):
        message = ""
        try:
            await asyncio.to_thread(self._recorder.start)
            if self._cancelled.is_set():
                return
            self._state = "recording"
            while not self._stop_requested.is_set() and not self._recorder.finished:
                seconds = int(self._recorder.elapsed)
                self._render(
                    f"Запись {seconds // 60:02d}:{seconds % 60:02d} / "
                    f"{MAX_RECORDING_SECONDS // 60:02d}:{MAX_RECORDING_SECONDS % 60:02d} · "
                    "Нажмите ■, когда закончите"
                )
                try:
                    await asyncio.wait_for(self._stop_requested.wait(), timeout=0.2)
                except asyncio.TimeoutError:
                    pass
            if self._cancelled.is_set():
                return
            self._state = "processing"
            self._render("Распознаю речь… При первом запуске загружается модель.")
            wav_bytes = await asyncio.to_thread(self._recorder.stop)
            text = await asyncio.to_thread(transcribe_audio, wav_bytes, self._cancelled)
            if not self._cancelled.is_set() and not self._closed:
                # Берём актуальный черновик: пользователь мог допечатать его во время распознавания.
                draft = self.prompt.value or ""
                separator = " " if draft and not draft[-1].isspace() else ""
                self.prompt.value = draft + separator + text
                self.prompt.update()
                await self.prompt.focus()
        except (CancelledError, asyncio.CancelledError):
            externally_cancelled = getattr(
                asyncio.current_task(), "cancelling", lambda: not self._cancelled.is_set(),
            )()
            self._cancelled.set()
            if externally_cancelled:
                raise
        except Exception as exc:
            if not self._cancelled.is_set():
                message = f"Диктовка: {exc}"
        finally:
            try:
                await asyncio.to_thread(self._recorder.cancel)
            except Exception:
                if not message and not self._cancelled.is_set():
                    message = "Не удалось освободить микрофон. Проверьте устройство в настройках системы."
            self._state = "idle"
            self._render(message)

    async def cancel(self, _=None):
        if not self.busy:
            self._render()
            return
        self._cancelled.set()
        self._stop_requested.set()
        self._state = "cancelling"
        self._render("Отменяю диктовку…")

    async def close(self, _=None):
        """При закрытии страницы освобождаем микрофон и отбрасываем поздний результат."""
        self._closed = True
        self._cancelled.set()
        self._stop_requested.set()
        if self._recorder is not None:
            await asyncio.to_thread(self._recorder.cancel)
