"""
Файл: tests/test_live.py
Разработчик: DenBroLiik
Описание: Проверки автоматических реплик, голосового цикла и отмены Live без БД и устройств.
"""

import asyncio
import io
import threading
import unittest
import wave
from concurrent.futures import CancelledError
from unittest.mock import Mock, patch

from App.app.live_conversation import LiveConversation
from App.services import live_audio, llm


class SegmentationTests(unittest.TestCase):
    def setUp(self):
        self.vad = Mock()
        self.frame = b"\x10\x00" * 480
        self.segment = live_audio.SpeechSegmenter(vad=self.vad)

    def feed(self, count, voiced):
        self.vad.is_speech.return_value = voiced
        for _ in range(count):
            self.segment.feed(self.frame)

    def test_idle_silence_keeps_only_preroll_and_does_not_trigger(self):
        self.feed(10000, False)
        self.assertFalse(self.segment.started)
        self.assertFalse(self.segment.finished)
        self.assertEqual(len(self.segment._pre_roll), 10)
        self.assertFalse(self.segment._chunks)

    def test_short_noise_does_not_become_a_question(self):
        self.feed(2, True)
        self.feed(40, False)
        self.assertFalse(self.segment.started)

    def test_speech_ends_after_pause_preserving_onset(self):
        self.feed(10, False)
        self.feed(10, True)
        self.feed(29, False)
        self.assertFalse(self.segment.finished)
        self.feed(1, False)
        self.assertTrue(self.segment.finished)
        with wave.open(io.BytesIO(self.segment.wav_bytes()), "rb") as wav:
            self.assertEqual(wav.getframerate(), 16000)
            self.assertEqual(wav.getnframes(), 44 * 480)

    def test_short_pause_does_not_split_utterance(self):
        self.feed(10, True)
        self.feed(10, False)
        self.feed(10, True)
        self.assertFalse(self.segment.finished)
        self.feed(30, False)
        self.assertTrue(self.segment.finished)

    def test_long_utterance_is_bounded_by_model_limit(self):
        self.feed(1200, True)
        with wave.open(io.BytesIO(self.segment.wav_bytes()), "rb") as wav:
            self.assertEqual(wav.getnframes(), 16000 * 30)

    def test_cancel_while_waiting_for_speech_releases_microphone(self):
        started = threading.Event()
        cancelled = threading.Event()
        stream = Mock()
        stream.start.side_effect = started.set
        backend = Mock(RawInputStream=Mock(return_value=stream))
        errors = []

        def run():
            try:
                live_audio.record_utterance(cancelled)
            except CancelledError:
                errors.append("cancelled")

        with patch.object(live_audio, "sd", backend):
            worker = threading.Thread(target=run)
            worker.start()
            self.assertTrue(started.wait(2))
            cancelled.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, ["cancelled"])
        stream.abort.assert_called_once()
        stream.close.assert_called_once()


class LiveControllerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock(web=False)
        self.history = []
        self.speaker = Mock()
        self.calls = []

        async def add_user(text):
            self.history.append({"role": "user", "content": text})

        async def add_ai(text):
            self.history.append({"role": "ai", "content": text})

        self.live = LiveConversation(self.page, lambda: False, lambda: list(self.history), add_user, add_ai)
        patches = {
            "check_live_audio": Mock(),
            "SpeechOutput": Mock(return_value=self.speaker),
            "prepare_voice_model": Mock(),
            "record_utterance": Mock(side_effect=self.wait_for_cancel),
            "transcribe_audio": Mock(return_value="Привет"),
            "generate_live_reply": Mock(return_value="Здравствуйте"),
        }
        self.mocks = patches
        for name, replacement in patches.items():
            patcher = patch(f"App.app.live_conversation.{name}", replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def wait_for_cancel(self, cancelled):
        if not cancelled.wait(3):
            raise RuntimeError("Test timed out waiting for cancellation")
        raise CancelledError()

    async def wait_state(self, state):
        async def wait():
            while self.live._state != state:
                await asyncio.sleep(0.005)
        await asyncio.wait_for(wait(), 3)

    async def finish(self):
        await asyncio.wait_for(asyncio.shield(self.live._task), 3)

    async def test_stop_during_listening_does_not_send_audio(self):
        await self.live.toggle()
        await self.wait_state("listening")
        await self.live.stop()
        await self.finish()
        self.assertFalse(self.live.busy)
        self.assertFalse(self.history)
        self.mocks["transcribe_audio"].assert_not_called()

    async def test_two_turns_share_history_and_return_to_listening(self):
        recordings = 0

        def record(cancelled):
            nonlocal recordings
            recordings += 1
            self.calls.append("listen")
            if recordings <= 2:
                return b"audio"
            return self.wait_for_cancel(cancelled)

        self.mocks["record_utterance"].side_effect = record
        self.speaker.speak.side_effect = lambda *_: self.calls.append("speak")
        await self.live.toggle()
        async def wait():
            while recordings < 3:
                await asyncio.sleep(0.005)
        await asyncio.wait_for(wait(), 3)
        await self.live.stop()
        await self.finish()
        self.assertEqual(self.calls, ["listen", "speak", "listen", "speak", "listen"])
        self.assertEqual([item["role"] for item in self.history], ["user", "ai", "user", "ai"])
        second_context = self.mocks["generate_live_reply"].call_args_list[1].args[0]
        self.assertEqual(len(second_context), 3)

    async def test_interrupt_speech_resumes_listening(self):
        self.mocks["record_utterance"].side_effect = None
        self.mocks["record_utterance"].return_value = b"audio"
        self.speaker.speak.side_effect = lambda _, cancelled: self.wait_for_cancel(cancelled)
        await self.live.toggle()
        await self.wait_state("speaking")
        self.mocks["record_utterance"].side_effect = self.wait_for_cancel
        await self.live.interrupt()
        await self.wait_state("listening")
        await self.live.stop()
        await self.finish()
        self.assertEqual(len(self.history), 2)

    async def test_stop_discards_late_model_reply(self):
        entered, release = threading.Event(), threading.Event()
        self.mocks["record_utterance"].side_effect = None
        self.mocks["record_utterance"].return_value = b"audio"

        def reply(*_):
            entered.set()
            release.wait(3)
            return "Поздний ответ"

        self.mocks["generate_live_reply"].side_effect = reply
        await self.live.toggle()
        self.assertTrue(await asyncio.to_thread(entered.wait, 2))
        await self.live.stop()
        release.set()
        await self.finish()
        self.assertEqual([item["role"] for item in self.history], ["user"])
        self.speaker.speak.assert_not_called()

    async def test_missing_voice_does_not_open_microphone(self):
        self.mocks["SpeechOutput"].side_effect = RuntimeError("Нет голоса")
        await self.live.toggle()
        await self.finish()
        self.mocks["record_utterance"].assert_not_called()
        self.assertIn("Нет голоса", self.live.status_text.value)
        self.assertFalse(self.live.busy)

    async def test_repeated_clicks_cancel_start_without_second_session(self):
        await self.live.toggle()
        await self.live.toggle()
        await self.finish()
        self.mocks["record_utterance"].assert_not_called()

    async def test_close_prevents_later_ui_updates(self):
        await self.live.toggle()
        await self.wait_state("listening")
        await self.live.close()
        updates = self.page.update.call_count
        await self.finish()
        self.assertEqual(updates, self.page.update.call_count)

    async def test_busy_mode_and_browser_do_not_start_live(self):
        self.live.is_busy = lambda: True
        await self.live.toggle()
        self.live.is_busy = lambda: False
        self.page.web = True
        await self.live.toggle()
        self.mocks["prepare_voice_model"].assert_not_called()


class LiveModelTests(unittest.TestCase):
    def test_text_followup_receives_previous_live_messages(self):
        conversation = Mock()
        conversation.send_message.return_value = {"content": [{"text": "Синий"}]}
        context = Mock(__enter__=Mock(return_value=conversation), __exit__=Mock(return_value=False))
        engine = Mock()
        engine.create_conversation.return_value = context
        history = [{"role": "user", "content": "Мой любимый цвет — синий"}]
        with patch.multiple(llm, _engine=engine, _conversation=Mock()), patch.object(llm, "record_generation"):
            self.assertEqual(llm.generate_reply("Какой цвет я назвал?", history=history), "Синий")
        self.assertEqual(engine.create_conversation.call_args.kwargs["messages"][0]["content"][0]["text"], history[0]["content"])
        self.assertEqual(conversation.send_message.call_args.args[0], "Какой цвет я назвал?")

    def test_reply_uses_fresh_context_and_keeps_chat_conversation_untouched(self):
        conversation = Mock()
        conversation.send_message.return_value = {"content": [{"text": "Привет"}]}
        context = Mock(__enter__=Mock(return_value=conversation), __exit__=Mock(return_value=False))
        engine = Mock()
        engine.create_conversation.return_value = context
        chat = Mock()
        history = [
            {"role": "user", "content": "Я Денис"},
            {"role": "ai", "content": "Привет, Денис"},
            {"role": "user", "content": "Как меня зовут?"},
        ]
        with patch.multiple(llm, _engine=engine, _conversation=chat, _supports_audio=True), patch.object(llm, "record_generation"):
            self.assertEqual(llm.generate_live_reply(history, threading.Event()), "Привет")
        messages = engine.create_conversation.call_args.kwargs["messages"]
        self.assertEqual([item["role"] for item in messages], ["user", "model"])
        self.assertEqual(conversation.send_message.call_args.args[0]["content"][0]["text"], "Как меня зовут?")
        chat.send_message.assert_not_called()
        context.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
