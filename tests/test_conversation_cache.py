"""Файл: /tests/test_conversation_cache.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Продолжение KV-сессии и её сброс при смене/редактировании/отмене чата.
"""
import threading
import unittest
from concurrent.futures import CancelledError
from unittest.mock import Mock, patch
from App.services import llm
from App.services.conversation_cache import ConversationCache


class WarmContextTests(unittest.TestCase):
    def setUp(self):
        self.cache = ConversationCache()
        self.engine = Mock()
        self.sessions = []
        def create(**kwargs):
            session = Mock()
            session.__enter__ = Mock(return_value=session)
            session.__exit__ = Mock(side_effect=lambda *a: session.close())
            session.send_message.return_value = {'content': [{'text': 'Ответ'}]}
            self.sessions.append(session)
            return session
        self.engine.create_conversation.side_effect = create
        self.patches = [patch.object(llm, '_warm_context', self.cache),
            patch.object(llm, '_engine', self.engine), patch.object(llm, 'litert_lm', object()),
            patch.object(llm, '_build_message', side_effect=lambda text, *a, **kw: text),
            patch.object(llm, '_fit_context', side_effect=lambda e, s, h, *a: h),
            patch.object(llm, 'response_language_instruction', return_value='ru'),
            patch.object(llm, 'record_generation')]
        for p in self.patches:p.start();self.addCleanup(p.stop)
        self.addCleanup(self.cache.clear)

    def first(self, **kwargs):
        return llm.generate_reply('Привет', history=[], cache_scope='one', **kwargs)

    def history(self):return [{'role': 'user', 'content': 'Привет'}, {'role': 'ai', 'content': 'Ответ'}]

    def test_exact_next_turn_reuses_native_session_without_prefilling_history_again(self):
        self.first()
        llm.generate_reply('Продолжи', history=self.history(), cache_scope='one')
        self.assertEqual(self.engine.create_conversation.call_count, 1)
        self.assertEqual(self.sessions[0].send_message.call_count, 2)
        self.assertEqual(self.cache.hits, 1)
        self.assertEqual(self.cache.history[-2]['content'][0]['text'], 'Продолжи')

    def test_edit_scope_system_schema_and_attachment_each_invalidate(self):
        for changed in [dict(history=[]), dict(cache_scope='two'), dict(instructions='new'),
                        dict(structured=True, response_schema={'type':'object'}),
                        dict(attachments=[('a.txt','/qa')]), dict(private=True)]:
            with self.subTest(changed=changed):
                self.cache.clear();self.first()
                old = self.sessions[-1]
                options = dict(history=self.history(), cache_scope='one');options.update(changed)
                llm.generate_reply('Продолжи', **options)
                old.close.assert_called_once()
                self.assertIsNot(self.cache.session, old)
                if changed.get('private') or changed.get('attachments'):
                    self.assertIsNone(self.cache.session)

    def test_cancelled_or_empty_reply_does_not_retain_partial_context(self):
        self.first()
        event=threading.Event();event.set()
        with patch.object(llm, '_send_cancellable', side_effect=CancelledError()), self.assertRaises(CancelledError):
            llm.generate_reply('Продолжи', history=self.history(), cache_scope='one', cancelled=event)
        self.assertIsNone(self.cache.session)
        self.first()
        self.sessions[-1].send_message.return_value={'content':[]}
        with self.assertRaises(RuntimeError):
            llm.generate_reply('Продолжи', history=self.history(), cache_scope='one')
        self.assertIsNone(self.cache.session)

    def test_auxiliary_call_is_ephemeral_and_unload_closes_context_before_engine(self):
        self.first()
        old=self.sessions[-1]
        llm.generate_reply('Извлеки факт', history=[])
        old.close.assert_called_once()
        self.assertIsNone(self.cache.session)
        self.first()
        events=[]
        self.cache.session.close.side_effect=lambda:events.append('context')
        self.engine.close.side_effect=lambda:events.append('engine')
        with patch.object(llm, '_conversation', None), patch.object(llm, 'release_unused_memory'):
            llm.unload_model()
        self.assertEqual(events, ['context','engine'])
