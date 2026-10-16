"""
Файл: /tests/test_settings_recovery_209.py
Разработчик: DenBroLiik
Версия: 2.0.9
Описание: Ограниченный viewport настроек, различимые сетевые ошибки и поддержка без зависания.
"""
import asyncio
import socket
import ssl
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,Mock,patch
from urllib.error import URLError
import flet as ft
from App.settings import main as settings
from App.services import platforms,cloud_account,support

class SettingsViewportTests(unittest.TestCase):
    def test_long_settings_remain_scrollable_after_keyboard_resize(self):
        page=SimpleNamespace(width=393,height=851,update=Mock())
        long=ft.Column(controls=[ft.Text(str(i)) for i in range(100)])
        with patch.object(settings,'build_account_page',return_value=long),patch.object(settings.navigation,'save'):
            dialog=settings.build_settings_dialog(page,start_section=0)
        host=dialog.content.controls[1].content.controls[0]
        self.assertIsInstance(host.content,ft.ListView)
        for height in (851,420,851):
            page.height=height;platforms.fit_dialog(page,dialog)
            self.assertGreater(host.content.height,0)
            self.assertLessEqual(host.content.height,dialog.content.height-120)
            self.assertEqual(len(host.content.controls[0].controls),100)
            self.assertEqual(host.content.scroll,ft.ScrollMode.ALWAYS)

    def test_network_errors_distinguish_tls_dns_and_timeout(self):
        for cause,expected in [(socket.gaierror(-2,'test'),'dns_failed'),
                (ssl.SSLCertVerificationError(1,'test'),'tls_failed'),(TimeoutError(),'connection_timeout')]:
            with self.subTest(expected=expected),patch.object(cloud_account,'build_opener') as opener,patch('App.services.cloud_traffic.reserve'):
                opener.return_value.open.side_effect=URLError(cause)
                with self.assertRaises(cloud_account.CloudError) as raised:
                    cloud_account._request('https://xopilot.by','/health')
                self.assertEqual(raised.exception.code,expected)

class SupportRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_mail_timeout_has_visible_recovery_message(self):
        with tempfile.TemporaryDirectory() as folder:
            archive=Path(folder)/'logs.zip';archive.write_bytes(b'QA')
            with patch.object(support,'is_android',return_value=True),patch.object(support,'collect',return_value=archive),patch('App.services.mobile_runtime.call_async',AsyncMock(side_effect=TimeoutError())):
                with self.assertRaisesRegex(RuntimeError,'Сохраните диагностику'):
                    await support.compose('QA','Synthetic test')
