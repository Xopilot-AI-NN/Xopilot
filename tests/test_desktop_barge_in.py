"""Файл: /tests/test_desktop_barge_in.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Отмена записи Live и освобождение собственного источника PipeWire.
"""
import threading
import unittest
from concurrent.futures import CancelledError
from unittest.mock import Mock, patch

from App.services import desktop_barge_in as audio


class DesktopRecordingTests(unittest.TestCase):
    def listener(self):
        listener = audio.DesktopBargeIn.__new__(audio.DesktopBargeIn)
        listener.process = Mock()
        listener.process.poll.return_value = None
        listener.name = 'xopilot_test_aec'
        listener._lock = threading.Lock()
        return listener

    def test_cancelled_recording_does_not_open_microphone(self):
        listener = self.listener()
        cancelled = threading.Event()
        cancelled.set()
        with patch.object(audio, 'check_live_audio'), patch.object(audio.subprocess, 'Popen') as spawn:
            with self.assertRaises(CancelledError):
                listener.record(cancelled, Mock())
        spawn.assert_not_called()

    def test_source_eof_releases_recorder_and_selector(self):
        listener = self.listener()
        recorder = Mock()
        selector = Mock()
        selector.select.return_value = [(None, None)]
        with patch.object(audio, 'check_live_audio'), \
                patch.object(audio.subprocess, 'Popen', return_value=recorder), \
                patch.object(audio.selectors, 'DefaultSelector', return_value=selector), \
                patch.object(audio, 'SpeechSegmenter') as segmenter, \
                patch.object(audio.os, 'read', return_value=b''):
            segmenter.return_value.finished = False
            with self.assertRaisesRegex(RuntimeError, 'завершил запись'):
                listener.record(threading.Event(), Mock())
        recorder.terminate.assert_called_once()
        recorder.wait.assert_called_once_with(timeout=2)
        recorder.stdout.close.assert_called_once()
        selector.close.assert_called_once()

    def test_close_is_idempotent_and_kills_unresponsive_module(self):
        listener = self.listener()
        process = listener.process
        process.wait.side_effect = [audio.subprocess.TimeoutExpired('pw-cli', 2), None]
        listener.close()
        listener.close()
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertIsNone(listener.process)


if __name__ == '__main__':
    unittest.main()
