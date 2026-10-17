"""Файл: /tests/test_message_duration.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Время ответа отдельно от текста и совместимость со старой историей.
"""
import unittest
from App.app.chat.messages.message import build_ai_message


class MessageDurationTests(unittest.TestCase):
    def test_short_and_long_durations_are_outside_copied_markdown(self):
        for seconds,label in ((12.75,'12.8 с'),(125.1,'2 мин 5 с')):
            message=build_ai_message('Сохранённый ответ',elapsed_seconds=seconds)
            bubble,footer=message.content.controls
            self.assertEqual(bubble.content.controls[0].value,'Сохранённый ответ')
            self.assertEqual(footer.controls[-1].value,'Время ответа · '+label)

    def test_legacy_or_invalid_duration_has_no_invented_time(self):
        for seconds in (None,-1,float('nan'),float('inf')):
            message=build_ai_message('Старый ответ',elapsed_seconds=seconds)
            self.assertEqual(len(message.content.controls[1].controls),1)
