"""Файл: /tests/test_history_sync_refresh.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Обновление открытой истории при удалении на другом устройстве без удержания окна в памяти.
"""
import gc
import importlib
import unittest
import weakref
from unittest.mock import Mock,patch

history=importlib.import_module('App.settings.history.list')


class HistorySyncTests(unittest.TestCase):
    def test_open_form_allows_outbound_deletion_but_defers_incoming_edits(self):
        from types import SimpleNamespace
        from App.app.tasks.sync_schedule import upload_only
        page=SimpleNamespace(_dialogs=SimpleNamespace(controls=[]),_xopilot_can_sync=lambda:True)
        self.assertFalse(upload_only(page))
        page._dialogs.controls=[SimpleNamespace(open=True)]
        self.assertTrue(upload_only(page))
        page._dialogs.controls=[SimpleNamespace(open=True,_xopilot_sync_safe=True)]
        self.assertFalse(upload_only(page))
        page._xopilot_can_sync=lambda:False
        self.assertTrue(upload_only(page))

    def test_open_history_reloads_after_remote_deletion(self):
        page=Mock();items=[(7,'Удаляемый чат','Сообщений: 0',False)]
        with patch.object(history,'list_chat_items',side_effect=lambda:list(items)), \
                patch.object(history,'load_chat_messages',return_value=[]), \
                patch.object(history,'chat_workspace',return_value={'name':'Все чаты'}):
            control=history.build_history_list(page)
            self.assertEqual(len(control.controls[2].controls),1)
            items.clear();page._xopilot_history_refresh()
            self.assertEqual(control.controls[2].controls,[])

    def test_page_refresh_callback_does_not_retain_closed_history(self):
        page=Mock()
        with patch.object(history,'list_chat_items',return_value=[]):
            control=history.build_history_list(page);reference=weakref.ref(control)
            del control;gc.collect()
            self.assertIsNone(reference())
            page._xopilot_history_refresh()
