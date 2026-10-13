"""
Файл: tests/test_updates.py
Разработчик: DenBroLiik
Описание: Проверка обновлений без сети и очистка истории при ошибке БД.
"""

import io
import json
import unittest
import urllib.error
from unittest.mock import Mock, patch

import flet as ft
from App.services import updates
from App.settings.history import main as history


class UpdateTests(unittest.TestCase):
    def test_new_and_current_versions(self):
        for version, phrase in [("v2.1.0", "Доступна"), ("v2.0.0", "актуальна")]:
            with self.subTest(version=version):
                response = io.BytesIO(json.dumps({"tag_name": version}).encode())
                with patch.object(updates.urllib.request, "urlopen", return_value=response):
                    self.assertIn(phrase, updates.check_updates())

    def test_unpublished_releases_are_not_reported_as_latest(self):
        error = urllib.error.HTTPError(updates.API_URL, 404, "Not found", None, io.BytesIO())
        self.addCleanup(error.close)
        with patch.object(updates.urllib.request, "urlopen", side_effect=error):
            self.assertIn("не опубликованы", updates.check_updates())

    def test_offline_does_not_report_success(self):
        with patch.object(updates.urllib.request, "urlopen", side_effect=OSError("offline")):
            with self.assertRaises(OSError):
                updates.check_updates()


class HistoryTests(unittest.TestCase):
    def test_database_error_preserves_visible_messages(self):
        chat = ft.ListView(controls=[ft.Text("Важное сообщение")])
        chat.update = Mock()
        status = Mock()
        page=Mock(width=800,height=800)
        page._xopilot_clear_all_history=None
        with patch.object(history,'clear_all_chats',side_effect=RuntimeError('disk error')),patch.object(history,'build_history_list',return_value=ft.Column()):
            view=history.build_history_page(chat,status,1,page=page)
            view.controls[1].on_click(None)
            confirm=page.show_dialog.call_args.args[0]
            confirm.actions[1].on_click(None)
        self.assertEqual(len(chat.controls), 1)
        self.assertIn("disk error", status.call_args.args[0])
