"""
Файл: /tests/test_support_and_recovery.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Приватность диагностики, реальный HTTP-повтор и восстановление открытия браузера.
"""
import asyncio
import json
import logging
from pathlib import Path
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch,AsyncMock,Mock
from App.services import support,api_chat,external_browser,mobile_runtime

class DiagnosticsTests(unittest.TestCase):
    def test_archive_excludes_chats_credentials_and_raw_errors(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(support,'app_data_dir',return_value=Path(folder)):
            support.install()
            record=logging.LogRecord('App.services.api_chat',logging.ERROR,'secret-path',1,
                'HTTP 500 Authorization: Bearer do-not-include user@example.invalid chat secret',(),None)
            text=support.SafeFormatter().format(record)
            self.assertIn('HTTP 500',text)
            self.assertNotIn('do-not-include',text);self.assertNotIn('user@',text);self.assertNotIn('secret-path',text)
            (Path(folder)/'xopilot.db').write_text('PRIVATE DATABASE')
            path=support.collect()
            with zipfile.ZipFile(path) as archive:
                self.assertNotIn('xopilot.db',archive.namelist())
                self.assertIn('system.json',archive.namelist())
            for handler in list(logging.getLogger().handlers):
                if getattr(handler,'_xopilot_safe_log',False):logging.getLogger().removeHandler(handler);handler.close()
    def test_vision_json_500_fallback_uses_actual_http_without_replaying_tools(self):
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append(data)
                if 'response_format' in data:self.send_response(500);self.end_headers();self.wfile.write(b'{}')
                else:
                    self.send_response(200);self.end_headers();self.wfile.write(b'{"choices":[{"message":{"content":"{\\"final\\":\\"ok\\"}"}}]}')
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        config={'url':f'http://127.0.0.1:{server.server_port}/v1','model':'vision-test','key':'test-only'}
        try:
            with patch.object(api_chat,'configuration',return_value=config),patch.object(api_chat,'record_generation'),patch.object(api_chat,'image_support',return_value=True),patch.object(api_chat,'build_attachment_message_parts',return_value=([],[b'\xff\xd8\xfftest'])):
                self.assertIn('ok',api_chat.generate_reply('test',structured=True))
            self.assertEqual(len(requests),2)
            self.assertIn('response_format',requests[0]);self.assertNotIn('response_format',requests[1])
            self.assertEqual(requests[0]['messages'],requests[1]['messages'])
        finally:server.shutdown();server.server_close();thread.join();api_chat._json_unsupported.discard((config['url'],config['model']))

class AsyncRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_google_dialog_is_visible_before_network_and_error_remains_cancellable(self):
        from App.settings.account import cloud as ui
        page=Mock()
        def offline(**kwargs):
            self.assertTrue(page.show_dialog.called)
            raise ui.cloud_account.CloudError('connection_failed')
        with patch.object(ui.cloud_account,'state',return_value=None),patch.object(ui.cloud_account,'begin_google',side_effect=offline):
            card=ui.build_cloud_card(page)
            card.content.controls[3].on_click(None)
            callback,*args=page.run_task.call_args.args
            await callback(*args)
        dialog=page.show_dialog.call_args.args[0]
        self.assertEqual(dialog.actions[0].content,'Назад')
        self.assertFalse(dialog.actions[0].disabled)
        page.pop_dialog.assert_not_called()

    async def test_native_browser_failure_uses_external_fallback(self):
        launcher=Mock(launch_url=AsyncMock(return_value=True))
        with patch.object(external_browser,'is_android',return_value=True),patch.object(mobile_runtime,'call_async',new=AsyncMock(side_effect=RuntimeError('native unavailable'))),patch('flet.UrlLauncher',return_value=launcher):
            await external_browser.open_external('https://xopilot.by/')
        launcher.launch_url.assert_awaited_once()
    async def test_keyboard_metrics_coalesce_before_layout(self):
        pending=[];changed=Mock();page=Mock()
        page.run_task=lambda callback,*args:pending.append(asyncio.create_task(callback(*args)))
        service=Mock()
        with patch.object(mobile_runtime,'_service',service):
            mobile_runtime.bind_viewport(page,changed)
            # Ignore the polling fallback in this deterministic event test.
            pending[0].cancel()
            for height in (700,650,500,440):service.on_metrics(Mock(data={'height':height,'keyboard':300}))
            await asyncio.gather(*pending,return_exceptions=True)
        changed.assert_called_once();self.assertEqual(page.__dict__['_xopilot_available_height'],440)
