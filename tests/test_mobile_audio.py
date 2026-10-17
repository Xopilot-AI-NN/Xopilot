"""Файл: /tests/test_mobile_audio.py
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: Отмена ожидания речи и освобождение микрофона Android.
"""
import base64
import threading
import unittest
from concurrent.futures import CancelledError
from unittest.mock import Mock, patch
from App.services import mobile_audio


class MobileRecordingTests(unittest.TestCase):
    def test_missing_pcm_stops_recording_instead_of_listening_forever(self):
        def call(method, arguments=None):
            if method == 'audioPollUtterance':
                return {'state': 'waiting', 'bytes': 0, 'peak': 0}
        with patch.object(mobile_audio.runtime, 'call', side_effect=call) as bridge, \
                patch.object(mobile_audio.time, 'monotonic', side_effect=[0, 10]):
            with self.assertRaisesRegex(RuntimeError, 'звук не поступает'):
                mobile_audio.record_utterance(threading.Event())
        self.assertEqual(bridge.call_args.args, ('audioCancel',))

    def test_waiting_recording_can_be_cancelled_without_long_bridge_request(self):
        cancelled = threading.Event()
        calls = []
        def call(method, arguments=None):
            calls.append(method)
            if method == 'audioPollUtterance':
                cancelled.set()
                return {'state': 'waiting'}
        with patch.object(mobile_audio.runtime, 'call', side_effect=call):
            with self.assertRaises(CancelledError):
                mobile_audio.record_utterance(cancelled)
        self.assertEqual(calls, ['audioBeginUtterance', 'audioPollUtterance', 'audioCancel'])

    def test_completed_pcm_becomes_wav_and_releases_recorder(self):
        pcm = b'\x01\x00' * 8000
        def call(method, arguments=None):
            if method == 'audioPollUtterance':
                return {'state': 'done', 'data': base64.b64encode(pcm).decode()}
        with patch.object(mobile_audio.runtime, 'call', side_effect=call) as bridge:
            data = mobile_audio.record_utterance(threading.Event())
        self.assertTrue(data.startswith(b'RIFF'))
        self.assertEqual(data[44:], pcm)
        self.assertEqual(bridge.call_args.args, ('audioCancel',))

    def test_barge_in_cancels_response_at_speech_onset_without_discarding_phrase(self):
        pcm = b'\x01\x00' * 6000
        events = []
        polls = iter([{'state': 'waiting', 'speechStarted': True},
                      {'state': 'waiting', 'speechStarted': True},
                      {'state': 'done', 'speechStarted': True,
                       'data': base64.b64encode(pcm).decode()}])
        def call(method, arguments=None):
            events.append((method, arguments))
            if method == 'audioPollUtterance':
                return next(polls)
        started = Mock()
        with patch.object(mobile_audio.runtime, 'call', side_effect=call):
            data = mobile_audio.record_barge_in(threading.Event(), started)
        started.assert_called_once_with()
        self.assertEqual(events[0], ('audioBeginUtterance', {'echoCancellation': True}))
        self.assertEqual(data[44:], pcm)
        self.assertEqual(events[-1][0], 'audioCancel')

    def test_native_error_also_releases_recorder(self):
        def call(method, arguments=None):
            if method == 'audioPollUtterance':
                return {'state': 'error', 'error': 'microphone disconnected'}
        with patch.object(mobile_audio.runtime, 'call', side_effect=call) as bridge:
            with self.assertRaisesRegex(RuntimeError, 'microphone disconnected'):
                mobile_audio.record_utterance(threading.Event())
        self.assertEqual(bridge.call_args.args, ('audioCancel',))
