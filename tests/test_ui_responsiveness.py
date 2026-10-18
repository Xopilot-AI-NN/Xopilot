"""Файл: /tests/test_ui_responsiveness.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Диагностика зависания без личных данных и остановка скрытой анимации.
"""
import asyncio
import logging
import time
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from App.services import ui_responsiveness, support
from App.app.shared.components.reply_activity import ReplyActivity
from App.app.materials import material


class ResponsivenessTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_screenshot_preview_does_not_decode_on_ui_thread(self):
        started, release = threading.Event(), threading.Event()
        def decode(path):
            started.set()
            release.wait(2)
            return b'jpeg-preview'
        import flet as ft
        with patch.object(material, 'image_preview', side_effect=decode) as decoder:
            tile = material.build_file_tile(ft.FilePickerFile(id=1, name='screen.png',
                path='/qa/screen.png', size=100))
            decoder.assert_not_called()
            preview = tile.content.controls[0]
            preview._mounted = True
            preview.update = Mock()
            task = asyncio.create_task(preview.load_preview())
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 1))
                await asyncio.sleep(.03)
                self.assertFalse(task.done())
                preview.will_unmount()
                release.set()
                await task
                preview.update.assert_not_called()
            finally:
                release.set()
                await asyncio.gather(task, return_exceptions=True)

    async def test_blocking_loop_is_recorded_without_local_variables(self):
        page = SimpleNamespace(_xopilot_ai_busy=lambda: True)
        task = asyncio.create_task(ui_responsiveness.monitor_ui(page))
        try:
            with self.assertLogs(ui_responsiveness.__name__, level='WARNING') as logs:
                await asyncio.sleep(.15)
                private_value = 'PRIVATE_PROMPT_AND_API_KEY'
                time.sleep(1.4)  # Deliberately simulate the bug on the UI thread.
                await asyncio.sleep(.1)
            self.assertEqual(len(logs.records), 1)
            text = support.SafeFormatter().format(logs.records[0])
            self.assertIn('UI_BLOCKED', text)
            self.assertNotIn(private_value, text)
            self.assertNotIn(private_value, logs.output[0])
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_hidden_activity_does_not_keep_updating_controls(self):
        activity = ReplyActivity()
        activity.update = Mock()
        task = asyncio.create_task(activity.pulse())
        try:
            await asyncio.sleep(.02)
            activity.update.assert_not_called()
            activity.set_active(True)
            await asyncio.sleep(.02)
            self.assertTrue(activity.update.called)
            activity.set_active(False)
            count = activity.update.call_count
            await asyncio.sleep(.6)
            self.assertEqual(activity.update.call_count, count)
            self.assertFalse(activity.visible)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    def test_diagnostics_only_accept_application_relative_code_frames(self):
        record = logging.LogRecord('App.services.ui_responsiveness', logging.WARNING,
            '', 1, 'untrusted secret text', (), None)
        record.ui_frames = ['app/main.py:42:on_send', '/home/private/secret.py:1:key',
                            'services/api_chat.py:70:generate_reply']
        text = support.SafeFormatter().format(record)
        self.assertIn('app/main.py:42:on_send', text)
        self.assertNotIn('/home/private', text)
        self.assertNotIn('untrusted secret text', text)
