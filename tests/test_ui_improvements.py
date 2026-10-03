"""
Файл: tests/test_ui_improvements.py
Разработчик: DenBroLiik
Описание: Сохраняемые пространства, выбранный чат, реальные переименования и восстановление черновиков.
"""
import json
import unittest
from unittest.mock import Mock, patch
from App.services import workspaces, chat_store
import test_real_answers


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.settings = {}
        self.db = Mock()
        self.db.get_setting.side_effect = self.settings.get
        self.db.set_setting.side_effect = self.settings.__setitem__
        patcher = patch.object(workspaces, "get_db", return_value=self.db)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_create_select_rename_and_delete_preserve_chats(self):
        item = workspaces.create_workspace("Проект")
        workspaces.assign_chat(10, item["id"])
        workspaces.select_workspace(item["id"])
        workspaces.rename_workspace(item["id"], "Мой проект")
        self.assertEqual(workspaces.list_workspaces()[1]["name"], "Мой проект")
        self.assertEqual(workspaces.filter_chats([(10, "Первый"), (20, "Второй")]), [(10, "Первый")])
        self.assertIn(item["id"], self.settings[workspaces.KEY])
        workspaces.delete_workspace(item["id"])
        self.assertEqual(workspaces.selected_workspace(), "all")
        self.assertEqual(len(workspaces.filter_chats([(10, "Первый"), (20, "Второй")])), 2)
        self.db.delete_chat.assert_not_called()

    def test_failed_write_does_not_change_saved_workspace(self):
        workspaces.create_workspace("Сохранённый")
        saved = self.settings[workspaces.KEY]
        self.db.set_setting.side_effect = RuntimeError("disk full")
        with self.assertRaises(RuntimeError):
            workspaces.create_workspace("Не сохранять")
        self.assertEqual(self.settings[workspaces.KEY], saved)

    def test_creation_saves_instructions_and_materials_in_one_write(self):
        item = workspaces.create_workspace('Проект', 'Условия', [{'name': 'brief.txt', 'path': '/material'}])
        self.db.set_setting.assert_called_once()
        saved = workspaces.list_workspaces()[1]
        self.assertEqual(saved['id'], item['id'])
        self.assertEqual(saved['instructions'], 'Условия')
        self.assertEqual(saved['materials'], [{'name': 'brief.txt', 'path': '/material'}])

    def test_invalid_workspace_and_empty_name_are_rejected(self):
        with self.assertRaises(ValueError):
            workspaces.create_workspace(" ")
        with self.assertRaises(ValueError):
            workspaces.select_workspace("missing")
        with self.assertRaises(ValueError):
            workspaces.delete_workspace("all")


class DraftTests(unittest.IsolatedAsyncioTestCase):
    setUp = test_real_answers.PersistenceUITests.setUp
    async def test_switch_restores_each_chat_draft(self):
        self.prompt.value = "Черновик первого"
        with patch("App.app.main.switch_active_chat"):
            switch = self.menu.call_args.kwargs["on_chats_click"]
            with patch("App.app.main.list_chat_items", return_value=[]), patch("App.app.main.workspaces.filter_chats", return_value=[]), patch("App.app.main.build_chats_dialog") as dialog:
                switch(None)
                select = dialog.call_args.kwargs["on_select_chat"]
                select(2)
                self.assertEqual(self.prompt.value, "")
                self.prompt.value = "Черновик второго"
                select(1)
                self.assertEqual(self.prompt.value, "Черновик первого")
                select(2)
                self.assertEqual(self.prompt.value, "Черновик второго")
