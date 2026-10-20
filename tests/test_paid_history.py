"""
Файл: /tests/test_paid_history.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Расшифровка истории заданий, проверка ответа сервера и условий тарифов.
          Исполнитель: Codex.
"""
import unittest
import uuid
from unittest.mock import patch
from App.services import billing,remote_tasks


class PaidHistoryTests(unittest.TestCase):
    def test_history_decrypts_task_and_reply_and_requests_selected_page(self):
        owner=str(uuid.uuid4());identifier=str(uuid.uuid4());key=b'z'*32
        with patch.object(remote_tasks,'credentials',return_value=({'account_id':owner},key)):
            item={'id':identifier,'state':'completed','updated_at':1792400000,
                  'task':remote_tasks.encode(identifier,'task',{'prompt':'Проверь проект'}),
                  'result':remote_tasks.encode(identifier,'result',{'reply':'Готово'})}
            response={'jobs':[item],'history_days':7,'has_more':False,'next_offset':51}
            with patch.object(remote_tasks.cloud,'request',return_value=response) as request:
                result=remote_tasks.history(50)
            request.assert_called_once_with('/remote/history?offset=50')
            self.assertEqual(result['jobs'][0]['task']['prompt'],'Проверь проект')
            self.assertEqual(result['jobs'][0]['result']['reply'],'Готово')
            # Ciphertext from another account must fail authentication.
            with patch.object(remote_tasks,'credentials',return_value=({'account_id':str(uuid.uuid4())},key)),patch.object(remote_tasks.cloud,'request',return_value=response):
                with self.assertRaises(Exception):remote_tasks.history(50)

    def test_invalid_pagination_is_rejected(self):
        with patch.object(remote_tasks,'credentials',return_value=({},b'z'*32)),patch.object(remote_tasks.cloud,'request') as request:
            for offset in (-1,True,100001):
                with self.assertRaises(ValueError):remote_tasks.history(offset)
            request.assert_not_called()
            request.return_value={'jobs':[],'history_days':365,'has_more':False,'next_offset':0}
            with self.assertRaises(ValueError):remote_tasks.history()

    def test_paid_storage_grows_without_disabling_free_features_or_checkout_gate(self):
        quotas={p['id']:p['quota_bytes'] for p in billing.PLANS}
        self.assertEqual(quotas,dict(micro=128*1024**2,elite=2*1024**3,ultra=10*1024**3,led=50*1024**3))
        self.assertTrue(all(not p['available'] for p in billing.PLANS if p['id']!='micro'))


class HistoryInterfaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_history_dialog_displays_decrypted_result_and_closes(self):
        from App.app.browser.remote_history import open_history
        class Page:
            height=740
            def show_dialog(self,value):self.dialog=value
            def pop_dialog(self):self.dialog=None
            def update(self):pass
            def run_task(self,call):self.load=call
        page=Page()
        payload={'jobs':[{'task':{'prompt':'Проверь сайт'},'result':{'reply':'Проверено'},'state':'completed','updated_at':1792400000}],
                 'history_days':7,'next_offset':1,'has_more':False}
        with patch.object(remote_tasks,'history',return_value=payload):
            open_history(page);await page.load()
        content=page.dialog.content.controls
        self.assertIn('7 дн.',content[0].value)
        self.assertEqual(content[1].controls[0].content.controls[0].value,'Проверь сайт')
        page.dialog.actions[0].on_click(None)
        self.assertIsNone(page.dialog)
