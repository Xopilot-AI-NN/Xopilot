"""
Файл: tests/test_native_db.py
Разработчик: DenBroLiik
Описание: Интеграционные проверки настоящей нативной БД в временном каталоге.
"""

from pathlib import Path
import tempfile
import unittest

from App.services.db import advanced_xopilot


@unittest.skipIf(advanced_xopilot is None, "Build native DB with scripts/build_native.py")
class NativeDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "test.db"
        self.db = advanced_xopilot.PyDatabase(str(self.path))
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.close)

    def close(self):
        self.db = None

    def test_reopen_keeps_settings_messages_and_attachments(self):
        chat = self.db.create_chat("Диалог")
        message = self.db.add_message(chat, "user", "Текст", None, None, [("a.txt", "/tmp/a.txt")])
        self.db.set_setting("voice", "maple")
        self.close()
        self.db = advanced_xopilot.PyDatabase(str(self.path))
        stored = self.db.get_messages(chat)
        self.assertEqual(stored[0].id, message)
        self.assertEqual(stored[0].attachments, [("a.txt", "/tmp/a.txt")])
        self.assertEqual(self.db.get_setting("voice"), "maple")
        self.assertEqual(self.db.schema_version(), 2)
        self.assertNotEqual(self.path.read_bytes()[:16], b"SQLite format 3\x00")

    def test_edit_delete_and_chat_cascade_persist(self):
        chat = self.db.create_chat("Диалог")
        message = self.db.add_message(chat, "user", "До")
        self.assertTrue(self.db.update_message(message, "После"))
        self.assertEqual(self.db.get_messages(chat)[0].content, "После")
        self.assertTrue(self.db.delete_message(message))
        self.assertFalse(self.db.delete_message(message))
        self.db.add_message(chat, "user", "Удалить", None, None, [("a", "/tmp/a")])
        self.assertTrue(self.db.delete_chat(chat))
        self.assertEqual(self.db.total_message_count(), 0)
        self.assertEqual(self.db.list_chats(), [])

    def test_invalid_chat_does_not_create_partial_message(self):
        with self.assertRaises(RuntimeError):
            self.db.add_message(99999, "user", "Не сохранять", None, None, [("a", "/tmp/a")])
        self.assertEqual(self.db.total_message_count(), 0)

    def test_editing_text_and_attachments_is_persistent(self):
        chat = self.db.create_chat("Материалы")
        message = self.db.add_message(chat, "user", "До", None, None, [("old.txt", "/tmp/old.txt")])
        self.assertTrue(self.db.update_message(message, "После", [("new.txt", "/tmp/new.txt")]))
        self.close()
        self.db = advanced_xopilot.PyDatabase(str(self.path))
        stored = self.db.get_messages(chat)[0]
        self.assertEqual((stored.content, stored.attachments), ("После", [("new.txt", "/tmp/new.txt")]))
        self.assertTrue(self.db.update_message(message, "Без файлов", []))
        self.assertEqual(self.db.get_messages(chat)[0].attachments, [])
        self.assertFalse(self.db.update_message(99999, "Не создавать", [("x", "/tmp/x")]))
        self.assertEqual(self.db.total_message_count(), 1)

    def test_clear_preserves_other_chat_and_settings(self):
        first, second = self.db.create_chat("Первый"), self.db.create_chat("Второй")
        self.db.add_message(first, "user", "Первый")
        self.db.add_message(second, "user", "Второй")
        self.db.set_setting("theme", "light")
        self.db.clear_chat_messages(first)
        self.assertEqual(self.db.get_messages(first), [])
        self.assertEqual(len(self.db.get_messages(second)), 1)
        self.assertEqual(self.db.get_setting("theme"), "light")

    def test_renaming_and_aggregate_counts_survive_reopen(self):
        chat = self.db.create_chat("До")
        self.db.add_message(chat, "user", "Вопрос")
        self.db.add_message(chat, "ai", "Ответ")
        self.assertTrue(self.db.rename_chat(chat, "После"))
        self.close()
        self.db = advanced_xopilot.PyDatabase(str(self.path))
        self.assertEqual(self.db.list_chat_summaries(), [(chat, "После", 2)])

    def test_selected_chat_survives_reset_of_python_cache(self):
        from unittest.mock import patch
        from App.services import chat_store
        first = self.db.create_chat("Первый")
        self.db.create_chat("Второй")
        with patch.object(chat_store, "get_db", return_value=self.db), patch.object(chat_store, "_active_chat_id", None):
            chat_store.switch_active_chat(first)
            chat_store._active_chat_id = None
            self.assertEqual(chat_store.get_or_create_active_chat_id(), first)
