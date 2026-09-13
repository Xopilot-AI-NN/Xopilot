"""
Файл: tests/test_piper_voice.py
Разработчик: DenBroLiik
Описание: Проверки отмены синтеза Piper и освобождения звукового выхода без устройств.
"""

import threading
import unittest
from concurrent.futures import CancelledError
from types import SimpleNamespace
from unittest.mock import Mock, patch

from App.services import piper_voice


class PiperVoiceTests(unittest.TestCase):
    def make_voice(self):
        voice = piper_voice.PiperSpeechVoice.__new__(piper_voice.PiperSpeechVoice)
        voice._lock = threading.Lock()
        voice._synthesis_config = object()
        voice._rate_scale = 1.0
        voice._run_options_factory = lambda: SimpleNamespace(terminate=False)
        voice._voice = Mock(session=Mock())
        return voice

    def test_cancel_interrupts_native_inference_and_next_turn_can_run(self):
        voice = self.make_voice()
        session = voice._voice.session
        cancelled = threading.Event()
        observations = []

        def run(*args, run_options):
            if not observations:
                cancelled.set()
                deadline = threading.Event()
                for _ in range(100):
                    if run_options.terminate:
                        observations.append("terminated")
                        raise RuntimeError("Native inference terminated")
                    deadline.wait(0.01)
                self.fail("Native inference did not receive cancellation")
            self.assertFalse(run_options.terminate)
            return ["audio"]

        session.run.side_effect = run

        def synthesize(*args, **kwargs):
            yield voice._voice.session.run(None, {})[0]

        voice._voice.synthesize.side_effect = synthesize
        with self.assertRaises(CancelledError):
            list(voice.synthesize("Первый ответ", cancelled))
        self.assertEqual(observations, ["terminated"])
        self.assertIs(voice._voice.session, session)
        self.assertFalse(voice._lock.locked())
        self.assertEqual(list(voice.synthesize("Следующий ответ", threading.Event())), ["audio"])

    def test_cancel_before_synthesis_does_not_run_model(self):
        voice = self.make_voice()
        cancelled = threading.Event()
        cancelled.set()
        with self.assertRaises(CancelledError):
            list(voice.synthesize("Привет", cancelled))
        voice._voice.synthesize.assert_not_called()
        self.assertFalse(voice._lock.locked())

    def test_inference_error_restores_session_and_releases_lock(self):
        voice = self.make_voice()
        session = voice._voice.session
        voice._voice.synthesize.side_effect = RuntimeError("Ошибка синтеза")
        with self.assertRaisesRegex(RuntimeError, "Ошибка синтеза"):
            list(voice.synthesize("Привет", threading.Event()))
        self.assertIs(voice._voice.session, session)
        self.assertFalse(voice._lock.locked())

    def playback(self, stream):
        voice = self.make_voice()
        self.synthesis_closed = False

        def synthesize(*_):
            try:
                yield SimpleNamespace(sample_rate=22050, sample_channels=1, audio_int16_bytes=b"\0\0" * 22050)
            finally:
                self.synthesis_closed = True

        voice.synthesize = synthesize
        backend = patch.object(piper_voice, "sd", Mock(RawOutputStream=Mock(return_value=stream)))
        backend.start()
        self.addCleanup(backend.stop)
        return voice

    def test_cancel_during_playback_stops_at_next_small_block_and_closes_audio(self):
        stream = Mock()
        cancelled = threading.Event()
        stream.write.side_effect = lambda _: cancelled.set()
        voice = self.playback(stream)
        with self.assertRaises(CancelledError):
            voice.speak("Привет", cancelled)
        self.assertTrue(self.synthesis_closed)
        stream.write.assert_called_once()
        self.assertLessEqual(len(stream.write.call_args.args[0]), 22050 * 2 * 0.04)
        stream.stop.assert_not_called()
        stream.abort.assert_called_once()
        stream.close.assert_called_once()

    def test_normal_playback_writes_all_audio_and_drains_output(self):
        stream = Mock()
        voice = self.playback(stream)
        voice.speak("Привет", threading.Event())
        self.assertEqual(sum(len(call.args[0]) for call in stream.write.call_args_list), 44100)
        stream.stop.assert_called_once()
        stream.close.assert_called_once()
        self.assertTrue(self.synthesis_closed)

    def test_output_start_failure_closes_generator_and_device(self):
        stream = Mock()
        stream.start.side_effect = RuntimeError("Устройство занято")
        voice = self.playback(stream)
        with self.assertRaisesRegex(RuntimeError, "Устройство занято"):
            voice.speak("Привет", threading.Event())
        stream.close.assert_called_once()
        self.assertTrue(self.synthesis_closed)


if __name__ == "__main__":
    unittest.main()
