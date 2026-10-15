"""
Файл: /tests/test_chat_digest.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Ограниченные выдержки других чатов, источники и сохранение нужного факта.
          Исполнитель проверок: Codex.
"""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from App.services import chat_search


class DigestTests(unittest.TestCase):
    def test_long_first_message_is_bounded_and_query_fact_survives(self):
        content='Лишняя переписка. '*5000+'Мой сайт https://xopilot.by, проект ОРИОН.'+' Другие сведения.'*5000
        db=Mock();db.list_chats.return_value=[(1,'Сайт',1),(-1,'Секрет',2)]
        db.get_messages.return_value=[SimpleNamespace(id=7,role='user',content=content,attachments=[])]
        with patch.object(chat_search,'get_db',return_value=db):
            result=chat_search.read(1,query='ОРИОН')
            self.assertLess(len(json.dumps(result,ensure_ascii=False)),4000)
            self.assertIn('https://xopilot.by',result['messages'][0]['content'])
            self.assertEqual(result['messages'][0]['message_id'],7)
            self.assertEqual(result['format'],'extractive_digest')
            with self.assertRaises(ValueError):chat_search.read(-1)
        db.get_messages.assert_called_once_with(1)

    def test_paging_does_not_return_whole_transcript_or_lose_cursor(self):
        db=Mock();db.list_chats.return_value=[(1,'История',1)]
        db.get_messages.return_value=[SimpleNamespace(id=i,role='user',content='Факт '+str(i)+' x'*1000,attachments=[]) for i in range(1,20)]
        with patch.object(chat_search,'get_db',return_value=db):
            first=chat_search.read(1)
            second=chat_search.read(1,after_message_id=first['next_after_message_id'])
        self.assertLessEqual(sum(len(m['content']) for m in first['messages']),2800)
        self.assertGreater(second['messages'][0]['message_id'],first['messages'][-1]['message_id'])

    def test_tool_payload_is_not_replayed_as_a_transcript(self):
        from App.app.task_summaries import PREFIX
        record=dict(label='Сайт',title='Проверка',state='Готово',summary='42',detail='PRIVATE_LARGE_PAYLOAD',tool='read_website',arguments_text='{}')
        self.assertNotIn('PRIVATE_LARGE_PAYLOAD',chat_search._excerpt(PREFIX+json.dumps(record)))
