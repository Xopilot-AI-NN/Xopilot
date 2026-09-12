"""
Файл: tests/test_dictation.py
Разработчик: DenBroLiik
Описание: Проверки записи, отмены, распознавания и сохранности черновика без устройств и БД.
"""

import asyncio
import io
import threading
import unittest
import wave
from array import array
from concurrent.futures import CancelledError
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import flet as ft

from App.app.voice_input import VoiceInput
from App.services import llm, microphone


class FakeStream:
    def __init__(self, **kwargs):
        self.callback = kwargs["callback"]
        self.finished_callback = kwargs["finished_callback"]
        self.closed = False

    def start(self):
        pass

    def abort(self):
        self.finished_callback()

    def close(self):
        self.closed = True


class MicrophoneTests(unittest.TestCase):
    def setUp(self):
        self.backend = SimpleNamespace(
            query_devices=Mock(return_value={"max_input_channels": 1, "default_samplerate": 16000}),
            RawInputStream=Mock(side_effect=FakeStream),
            CallbackStop=type("CallbackStop", (Exception,), {}),
            CallbackAbort=type("CallbackAbort", (Exception,), {}),
        )
        self.patch = patch.object(microphone, "sd", self.backend)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.recorder = microphone.MicrophoneRecorder(max_seconds=1)
        self.addCleanup(self.recorder.cancel)

    def feed(self, frames, amplitude=400):
        self.recorder._stream.callback(array("h", [amplitude] * frames).tobytes(), frames, None, False)

    def test_stop_returns_valid_wav_and_releases_microphone(self):
        self.recorder.start()
        stream = self.recorder._stream
        self.feed(8000)
        with wave.open(io.BytesIO(self.recorder.stop()), "rb") as wav:
            self.assertEqual((wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()),
                             (16000, 1, 2, 8000))
        self.assertTrue(stream.closed)
        self.assertFalse(self.recorder._chunks)

    def test_capture_limit_trims_last_block(self):
        self.recorder.start()
        self.feed(12000)
        with self.assertRaises(self.backend.CallbackStop):
            self.feed(8000)
        with wave.open(io.BytesIO(self.recorder.stop()), "rb") as wav:
            self.assertEqual(wav.getnframes(), 16000)

    def test_cancel_discards_audio_and_allows_new_recording(self):
        self.recorder.start()
        stream = self.recorder._stream
        self.feed(8000)
        self.recorder.cancel()
        self.assertTrue(stream.closed)
        self.assertFalse(self.recorder._chunks)
        self.recorder.start()
        self.feed(8000)
        self.assertTrue(self.recorder.stop().startswith(b"RIFF"))

    def test_empty_short_and_silent_recordings_are_rejected(self):
        for frames, amplitude in [(0, 400), (1000, 400), (8000, 0)]:
            with self.subTest(frames=frames, amplitude=amplitude):
                self.recorder.start()
                stream = self.recorder._stream
                self.feed(frames, amplitude)
                with self.assertRaises(RuntimeError):
                    self.recorder.stop()
                self.assertTrue(stream.closed)

    def test_device_error_does_not_leave_stream_open(self):
        stream = FakeStream(callback=None, finished_callback=lambda: None)
        stream.start = Mock(side_effect=RuntimeError("Device disconnected"))
        self.backend.RawInputStream.side_effect = None
        self.backend.RawInputStream.return_value = stream
        with self.assertRaisesRegex(RuntimeError, "Не удалось включить микрофон"):
            self.recorder.start()
        self.assertTrue(stream.closed)

    def test_overflow_is_reported_instead_of_transcribing_incomplete_audio(self):
        self.recorder.start()
        self.feed(8000)
        with self.assertRaises(self.backend.CallbackAbort):
            self.recorder._stream.callback(b"", 0, None, True)
        with self.assertRaisesRegex(RuntimeError, "прервалась"):
            self.recorder.stop()

    def test_missing_portaudio_is_a_recoverable_error(self):
        with patch.object(microphone, "sd", None):
            with self.assertRaisesRegex(RuntimeError, "PortAudio"):
                self.recorder.start()


class VoiceInputTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock(web=False)
        self.prompt = SimpleNamespace(value="Черновик", update=Mock(), focus=AsyncMock())
        self.recorder = Mock(elapsed=0, finished=False)
        self.recorder.stop.return_value = b"wav audio"
        self.record_patch = patch("App.app.voice_input.MicrophoneRecorder", return_value=self.recorder)
        self.record_patch.start()
        self.addCleanup(self.record_patch.stop)
        self.transcribe_patch = patch("App.app.voice_input.transcribe_audio", return_value="Привет мир.")
        self.transcribe = self.transcribe_patch.start()
        self.addCleanup(self.transcribe_patch.stop)
        self.voice = VoiceInput(self.page, self.prompt, lambda: False)

    async def wait_for_state(self, state):
        async def wait():
            while self.voice._state != state:
                await asyncio.sleep(0.005)
        await asyncio.wait_for(wait(), timeout=3)

    async def finish(self):
        await asyncio.wait_for(asyncio.shield(self.voice._task), timeout=3)

    async def test_stop_appends_to_current_draft_without_sending(self):
        await self.voice.toggle()
        await self.wait_for_state("recording")
        self.prompt.value = "Черновик дополнен"
        await self.voice.toggle()
        await self.finish()
        self.assertEqual(self.prompt.value, "Черновик дополнен Привет мир.")
        self.assertFalse(self.voice.busy)
        self.recorder.stop.assert_called_once()
        self.prompt.focus.assert_awaited_once()
        self.transcribe.assert_called_once()

    async def test_cancel_preserves_draft_and_does_not_transcribe(self):
        await self.voice.toggle()
        await self.wait_for_state("recording")
        await self.voice.cancel()
        await self.finish()
        self.assertEqual(self.prompt.value, "Черновик")
        self.transcribe.assert_not_called()
        self.recorder.cancel.assert_called()
        self.assertFalse(self.voice.busy)

    async def test_repeated_clicks_do_not_start_multiple_recordings(self):
        await self.voice.toggle()
        await self.voice.toggle()
        await self.wait_for_state("recording")
        await self.voice.toggle()
        await self.voice.toggle()
        await self.finish()
        self.recorder.start.assert_called_once()
        self.transcribe.assert_called_once()

    async def test_limit_automatically_stops_and_transcribes(self):
        self.recorder.finished = True
        await self.voice.toggle()
        await self.finish()
        self.assertEqual(self.prompt.value, "Черновик Привет мир.")

    async def test_error_preserves_draft_and_restores_button(self):
        self.recorder.start.side_effect = RuntimeError("Нет микрофона")
        await self.voice.toggle()
        await self.finish()
        self.assertEqual(self.prompt.value, "Черновик")
        self.assertIn("Нет микрофона", self.voice.status_text.value)
        self.assertFalse(self.voice.button.disabled)
        self.assertEqual(self.voice.button.content.icon, ft.Icons.MIC)

    async def test_cancel_inference_discards_late_result(self):
        entered, release = threading.Event(), threading.Event()

        def transcribe(*_):
            entered.set()
            release.wait(3)
            return "Поздний результат"

        self.transcribe.side_effect = transcribe
        self.recorder.finished = True
        await self.voice.toggle()
        self.assertTrue(await asyncio.to_thread(entered.wait, 3))
        await self.voice.cancel()
        release.set()
        await self.finish()
        self.assertEqual(self.prompt.value, "Черновик")
        self.assertFalse(self.voice.busy)

    async def test_transcription_error_keeps_draft_and_allows_retry(self):
        self.recorder.finished = True
        self.transcribe.side_effect = RuntimeError("Модель недоступна")
        await self.voice.toggle()
        await self.finish()
        self.assertEqual(self.prompt.value, "Черновик")
        self.assertIn("Модель недоступна", self.voice.status_text.value)
        self.transcribe.side_effect = None
        await self.voice.toggle()
        await self.finish()
        self.assertEqual(self.prompt.value, "Черновик Привет мир.")

    async def test_close_during_microphone_start_releases_device(self):
        entered, release = threading.Event(), threading.Event()

        def start():
            entered.set()
            release.wait(3)

        self.recorder.start.side_effect = start
        await self.voice.toggle()
        self.assertTrue(await asyncio.to_thread(entered.wait, 3))
        await self.voice.close()
        updates = self.page.update.call_count
        release.set()
        await self.finish()
        self.assertEqual(self.page.update.call_count, updates)
        self.transcribe.assert_not_called()
        self.recorder.cancel.assert_called()

    async def test_busy_chat_and_browser_do_not_open_microphone(self):
        self.voice.is_sending = lambda: True
        await self.voice.toggle()
        self.recorder.start.assert_not_called()
        self.voice.is_sending = lambda: False
        self.page.web = True
        await self.voice.toggle()
        self.recorder.start.assert_not_called()


class TranscriptionTests(unittest.TestCase):
    def setUp(self):
        self.conversation = Mock()
        self.conversation.send_message.return_value = {"content": [{"type": "text", "text": "Привет."}]}
        self.context = Mock()
        self.context.__enter__ = Mock(return_value=self.conversation)
        self.context.__exit__ = Mock(return_value=False)
        self.engine = Mock()
        self.engine.create_conversation.return_value = self.context
        self.chat_conversation = Mock()
        self.patch = patch.multiple(llm, _engine=self.engine, _conversation=self.chat_conversation, _supports_audio=True)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_audio_uses_separate_conversation_and_no_chat_statistics(self):
        with patch.object(llm, "record_generation") as stats:
            text = llm.transcribe_audio(b"wav", threading.Event())
        self.assertEqual(text, "Привет.")
        self.chat_conversation.send_message.assert_not_called()
        stats.assert_not_called()
        contents = self.conversation.send_message.call_args.args[0].to_json()
        self.assertEqual(contents[1], {"type": "audio", "blob": "d2F2"})
        self.context.__exit__.assert_called_once()

    def test_cancellation_stops_native_inference_before_closing_conversation(self):
        cancelled, native_cancelled = threading.Event(), threading.Event()
        self.conversation.cancel_process.side_effect = native_cancelled.set

        def send(*_):
            cancelled.set()
            self.assertTrue(native_cancelled.wait(2))
            return {"content": []}

        self.conversation.send_message.side_effect = send
        with self.assertRaises(CancelledError):
            llm.transcribe_audio(b"wav", cancelled)
        self.context.__exit__.assert_called_once()

    def test_cancelled_job_does_not_load_or_use_model(self):
        cancelled = threading.Event()
        cancelled.set()
        with self.assertRaises(CancelledError):
            llm.transcribe_audio(b"wav", cancelled)
        self.engine.create_conversation.assert_not_called()

    def test_missing_audio_support_and_empty_transcript_are_reported(self):
        with patch.object(llm, "_supports_audio", False):
            with self.assertRaisesRegex(RuntimeError, "не поддерживает звук"):
                llm.transcribe_audio(b"wav", threading.Event())
        self.conversation.send_message.return_value = {"content": []}
        with self.assertRaisesRegex(RuntimeError, "Речь не распознана"):
            llm.transcribe_audio(b"wav", threading.Event())

    def test_missing_model_is_reported_without_downloading(self):
        with patch.object(llm, "_engine", None), patch.object(llm, "list_local_models", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "нужна локальная модель"):
                llm.transcribe_audio(b"wav", threading.Event())
        self.engine.create_conversation.assert_not_called()


if __name__ == "__main__":
    unittest.main()
