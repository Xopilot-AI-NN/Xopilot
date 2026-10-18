"""Файл: /tests/test_context_budget.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Сжатие переполненной истории без изменения исходной переписки.
"""
import copy
import threading
import unittest
from concurrent.futures import CancelledError
from App.services import context_budget as budget


class Engine:
    max_num_tokens = 4096
    def tokenize(self, text): return list(range(len(text)))


class ContextTests(unittest.TestCase):
    def setUp(self): budget._summaries.clear()

    def test_small_history_is_unchanged_without_model_call(self):
        history = [{'role': 'user', 'content': 'Имя — Денис'}]
        def unexpected(*args): self.fail('Unnecessary summary')
        self.assertEqual(budget.prepare(Engine(), 'system', history, 'current', unexpected), history)

    def test_overflow_chunks_fit_and_latest_turns_and_original_survive(self):
        engine = Engine()
        history = [{'role': 'user', 'content': str(i) + ':' + 'a' * 500} for i in range(20)]
        history.append({'role': 'user', 'content': 'Последнее уточнение'})
        original = copy.deepcopy(history)
        sources = []
        def summarize(system, text, target):
            self.assertLess(budget.count(engine, system + text) + target, 4096)
            sources.append(text)
            return 'Имя Денис; проект Xopilot; команды требуют подтверждения.'
        result = budget.prepare(engine, 'system', history, 'current', summarize)
        self.assertTrue(sources)
        self.assertEqual(history, original)
        self.assertEqual(result[-1], history[-1])
        self.assertLess(budget.count(engine, result) + 100, 3482)
        calls = len(sources)
        self.assertEqual(budget.prepare(engine, 'system', history, 'current', summarize), result)
        self.assertEqual(len(sources), calls)

    def test_bad_numeric_fact_is_retried_and_important_middle_instruction_is_verbatim(self):
        history = [{'role': 'user', 'content': 'Имя Денис'}]
        history += [{'role': 'model', 'content': 'filler ' * 100} for _ in range(8)]
        fact = {'role': 'user', 'content': 'Порт 7799. Файл src/server.py. Не удаляй файлы.'}
        history.insert(4, fact)
        calls = []
        def summarize(system, text, target):
            calls.append(system)
            # Simulate a wrong port only on a fragment that contains the real one.
            if '7799' in text and 'Не изменяй числа' not in system:
                return 'Порт 7999, файл src/server.py'
            return 'Порт 7799, файл src/server.py' if '7799' in text else 'Обсуждение интерфейса'
        result = budget.prepare(Engine(), '', history, 'current', summarize)
        self.assertIn(fact, result)
        self.assertTrue(any('Не изменяй числа' in c for c in calls))
        self.assertNotIn('7999', str(result))

    def test_unverified_numeric_summary_cannot_override_a_verbatim_user_fact(self):
        fact = {'role':'user', 'content':'Порт 7799. Не удаляй файлы.'}
        history = [fact, {'role':'model', 'content':'x' * 6000}]
        result = budget.prepare(Engine(), '', history, 'current', lambda *args:'Порт 7999')
        self.assertIn(fact, result)
        self.assertNotIn('7999', str(result))
        self.assertIn('неподтверждённое значение', str(result))

    def test_summary_respects_the_provider_output_limit(self):
        engine = Engine()
        engine.max_output_tokens = 64
        def summarize(system, text, target):
            self.assertLessEqual(target, 64)
            return 'summary'
        budget.prepare(engine, '', [{'role':'user', 'content':'x' * 6000}], 'current', summarize)

    def test_oversized_current_request_is_reported_without_silently_cutting_it(self):
        current = 'important request ' * 1000
        with self.assertRaisesRegex(RuntimeError, 'текущий запрос'):
            budget.prepare(Engine(), '', [], current, lambda *args:self.fail('No space for summary'))
        self.assertEqual(current, 'important request ' * 1000)

    def test_long_message_keeps_literal_middle_facts_even_with_corrupt_summary(self):
        history = [{'role':'user', 'content':'Обсуждаем внешний вид. ' * 160 +
                    'Порт 7799. Файл src/server.py. Не удаляй файлы. ' + 'Продолжаем. ' * 80}]
        original = copy.deepcopy(history)
        result = budget.prepare(Engine(), '', history, 'Какой порт и файл?', lambda *args:'Порт 7999')
        quoted = ' '.join(budget._text(item) for item in result[1:])
        self.assertIn('Порт 7799.', quoted)
        self.assertIn('Файл src/server.py.', quoted)
        self.assertNotIn('7999', str(result))
        self.assertEqual(history, original)

    def test_questions_are_not_fact_anchors_and_corrections_keep_order(self):
        history = [{'role':'user','content':'Как меня зовут?'},
                   {'role':'user','content':'Порт 7799.'},
                   {'role':'user','content':'Исправление: порт 8800 вместо 7799.'}]
        result = budget._anchors(Engine(), history, 300, 'порт')
        self.assertEqual([item['content'] for item in result], [item['content'] for item in history[1:]])

    def test_fact_before_a_question_is_preserved_without_the_question(self):
        result=budget._anchors(Engine(),[{'role':'user','content':'Меня зовут Денис. Как меня зовут?'}],300,'имя')
        self.assertEqual(result,[{'role':'user','content':'Меня зовут Денис.'}])

    def test_failed_summary_never_silently_discards_history(self):
        history = [{'role': 'user', 'content': 'a' * 5000}]
        original = copy.deepcopy(history)
        with self.assertRaisesRegex(RuntimeError, 'не создала сводку'):
            budget.prepare(Engine(), 'system', history, 'current', lambda *args: '')
        self.assertEqual(history, original)

    def test_cancelled_compaction_does_not_call_model(self):
        event = threading.Event(); event.set()
        with self.assertRaises(CancelledError):
            budget.prepare(Engine(), '', [{'role': 'user', 'content': 'a' * 5000}], '',
                           lambda *args: self.fail('cancelled'), cancelled=event)

    def test_private_summaries_are_not_cached(self):
        budget.prepare(Engine(), '', [{'role': 'user', 'content': 'a' * 5000}], '',
                       lambda *args: 'summary', private=True)
        self.assertFalse(budget._summaries)

    def test_image_bytes_are_not_counted_as_base64_text(self):
        self.assertEqual(budget.count(Engine(), {'type': 'image', 'data': 'x' * 1000000}), 1024)
