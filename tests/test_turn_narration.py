"""Файл: /tests/test_turn_narration.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Один ответ задачи, сохранение файлов/времени и появление нового текста.
"""
import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from App.services.db import advanced_xopilot
from App.app.tasks.turn_narration import TurnNarration
from App.app.chat.messages.message import build_ai_message


@unittest.skipIf(advanced_xopilot is None, 'Native database required')
class NarrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = advanced_xopilot.PyDatabase(str(Path(temp.name)/'qa.db'), 'a'*64)
        self.addCleanup(self.db.close)
        self.chat = self.db.create_chat('QA')
        def save(text, attachments=None, elapsed_seconds=None):
            return self.db.add_message(self.chat, 'ai', text,
                attachments=attachments or [], elapsed_seconds=elapsed_seconds)
        self.narration = TurnNarration(
            save,
            self.db.update_message, self.db.set_message_elapsed)

    async def test_comments_and_final_are_one_persistent_message_with_files_and_time(self):
        first = await self.narration.append('Смотрю приложения')
        await self.narration.append('Просматриваю экран')
        final = await self.narration.finish('Готово', [('result.txt','/qa/result.txt')], 2.5)
        self.assertEqual(final[0], first[0])
        rows = self.db.get_messages(self.chat)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].content, 'Смотрю приложения\n\nПросматриваю экран\n\nГотово')
        self.assertEqual(rows[0].attachments, [('result.txt','/qa/result.txt')])
        self.assertEqual(rows[0].elapsed_seconds, 2.5)
        await self.narration.finish('Готово', seconds=2.5)
        self.assertEqual(len(self.db.get_messages(self.chat)), 1)
        self.assertEqual(self.db.get_messages(self.chat)[0].content, rows[0].content)

    async def test_parallel_comments_do_not_create_duplicates(self):
        await asyncio.gather(*(self.narration.append(f'Шаг {i}') for i in range(4)))
        rows = self.db.get_messages(self.chat)
        self.assertEqual(len(rows), 1)
        for i in range(4): self.assertIn(f'Шаг {i}', rows[0].content)

    async def test_deleted_message_is_not_resurrected_by_final_answer(self):
        identifier, _, _ = await self.narration.append('Начал')
        self.db.delete_message(identifier)
        with self.assertRaisesRegex(RuntimeError, 'удалено'):
            await self.narration.finish('Готово')
        self.assertEqual(self.db.get_messages(self.chat), [])


class TextRevealTests(unittest.IsolatedAsyncioTestCase):
    async def test_animated_reply_finishes_with_complete_text_and_keeps_message_id(self):
        text = 'Смотрю экран.\n\nНашёл нужное окно.'
        message = build_ai_message(text, message_id=42, animate=True, reveal_from=13)
        body = message.content.controls[0].content.controls[0]
        message.update = Mock(); body.update = Mock()
        message._entrance_mounted = True
        await message.reveal()
        self.assertEqual(body.value, text)
        self.assertEqual(message.data, 42)

    def test_history_and_long_code_are_not_repeatedly_retyped(self):
        text = 'Код\n'+'x = 1\n'*2000
        history = build_ai_message(text)
        self.assertEqual(history.content.controls[0].content.controls[0].value, text)
        animated = build_ai_message(text, animate=True)
        self.assertFalse(hasattr(animated, '_text_reveal'))

    def test_progress_is_collapsed_and_final_answer_has_no_bubble(self):
        text='<!-- xopilot:progress -->\n> Открываю приложение\n\n> Проверяю окно\n\nГотово.'
        message=build_ai_message(text)
        status,bubble,footer=message.content.controls
        self.assertFalse(status.expanded)
        self.assertEqual(status.controls[0].value,'Открываю приложение\n\nПроверяю окно')
        self.assertEqual(bubble.content.controls[0].value,'Готово.')
        self.assertIsNone(bubble.bgcolor)

    def test_final_quote_is_not_treated_as_a_progress_note(self):
        from App.app.chat.messages.message import split_public_progress
        progress,answer=split_public_progress('<!-- xopilot:progress -->\n> Ищу\n\n<!-- xopilot:answer -->\n> Цитата из результата')
        self.assertEqual(progress,'Ищу')
        self.assertEqual(answer,'> Цитата из результата')
