"""
Файл: /tests/test_remote_tasks.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Диагностика отсутствующего сервера и завершение фонового приёма заданий.
          Исполнитель: Codex.
"""
import threading
import unittest
from unittest.mock import Mock,patch
from App.services import remote_tasks as remote


class RemoteTests(unittest.TestCase):
    def test_missing_server_route_is_explained_without_exposing_credentials(self):
        from App.services.cloud_account import CloudError
        with patch.object(remote,'credentials'),patch.object(remote.cloud,'request',side_effect=CloudError('server_error',404)):
            with self.assertRaisesRegex(ValueError,'обновление серверной части'):remote.hosts()

    def test_shutdown_cancels_active_task_and_stops_polling(self):
        cancelled=threading.Event();stop=threading.Event();thread=Mock()
        with patch.object(remote,'_cancel',cancelled),patch.object(remote,'_stop',stop),patch.object(remote,'_thread',thread):
            remote.shutdown()
        self.assertTrue(cancelled.is_set());self.assertTrue(stop.is_set());thread.join.assert_called_once_with(timeout=5)

    def test_key_missing_cannot_request_remote_host(self):
        with patch.object(remote.cloud,'state',return_value={'account_id':'qa'}),patch.object(remote,'get_db') as db,patch.object(remote.cloud,'request') as request:
            db.return_value.get_setting.return_value=None
            with self.assertRaisesRegex(ValueError,'пароль'):remote.hosts()
            request.assert_not_called()

    def test_remote_computer_approval_does_not_require_file_diff_fields(self):
        from App.app.remote_browser import approval_content
        for kind in ('device','computer_session'):
            title,preview=approval_content({'kind':kind,'title':'Кнопка QA','arguments':{'action':'click','target':'id'}})
            self.assertEqual(title,'Кнопка QA');self.assertIn('click',preview)
