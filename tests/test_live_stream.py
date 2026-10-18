"""Файл: /tests/test_live_stream.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Поток ответа Live, сбор фраз и завершение нативной генерации при отмене.
"""
import threading
import unittest
from concurrent.futures import CancelledError
from unittest.mock import Mock, patch
from App.services import llm, mobile_litert
from App.services.live_sentences import LiveSentences


class LiveStreamTests(unittest.TestCase):
    def test_sentences_keep_split_words_decimal_and_final_tail(self):
        sentences = LiveSentences()
        self.assertEqual(sentences.feed('Цена 3.'), [])
        self.assertEqual(sentences.feed('14 рубля. След'), ['Цена 3.14 рубля.'])
        self.assertEqual(sentences.feed('ующая фраза!\nХвост'), ['Следующая фраза!'])
        self.assertEqual(sentences.feed('', final=True), ['Хвост'])

    def test_model_yields_before_generation_finishes_without_duplicate_text(self):
        events = []
        def stream(message):
            events.append('start')
            yield {'content': [{'text': 'Первая фраза. '}]}
            self.assertEqual(events[-1], 'heard')
            yield {'content': [{'text': 'Вторая.'}]}
            events.append('done')
        conversation = Mock(send_message_async=stream)
        answer = llm._send_cancellable(conversation, 'Вопрос', threading.Event(),
                                      on_text=lambda text: events.append('heard'))
        self.assertEqual(llm._extract_text(answer), 'Первая фраза. Вторая.')
        self.assertEqual(events, ['start', 'heard', 'heard', 'done'])
        conversation.send_message.assert_not_called()

    def test_cancel_drains_completion_and_drops_late_chunks(self):
        cancelled = threading.Event()
        finished = []
        def stream(message):
            yield {'content': [{'text': 'Первая.'}]}
            yield {'content': [{'text': 'Не произносить.'}]}
            finished.append(True)
        heard = []
        def accept(text):
            heard.append(text)
            cancelled.set()
        conversation = Mock(send_message_async=stream)
        with self.assertRaises(CancelledError):
            llm._send_cancellable(conversation, 'Вопрос', cancelled, on_text=accept)
        self.assertEqual(heard, ['Первая.'])
        self.assertEqual(finished, [True])
        conversation.cancel_process.assert_called()

    def test_android_polls_chunks_until_native_completion(self):
        states = iter([{'chunks': ['Один. '], 'done': False},
                       {'chunks': ['Два.'], 'done': True}])
        def call(method, args):
            if method == 'streamPoll': return next(states)
        with patch.object(mobile_litert.runtime, 'call', side_effect=call) as bridge, \
                patch.object(mobile_litert.time, 'sleep'):
            chunks = list(mobile_litert.Conversation('qa').send_message_async('Вопрос'))
        self.assertEqual(''.join(llm._extract_text(c) for c in chunks), 'Один. Два.')
        self.assertEqual(bridge.call_args_list[0].args,
                         ('streamStart', {'id': 'qa', 'content': 'Вопрос'}))

    def test_android_error_is_not_a_successful_partial_reply(self):
        with patch.object(mobile_litert.runtime, 'call', side_effect=[None,
                {'chunks': [], 'done': True, 'error': 'GPU failed'}]):
            with self.assertRaisesRegex(RuntimeError, 'GPU failed'):
                list(mobile_litert.Conversation('qa').send_message_async('Вопрос'))
