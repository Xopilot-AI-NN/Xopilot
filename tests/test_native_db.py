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
        if self.db is not None:
            self.db.close()
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
        self.assertEqual(self.db.schema_version(), 3)
        self.assertNotEqual(self.path.read_bytes()[:16], b"SQLite format 3\x00")

    def test_elapsed_is_atomic_persistent_and_roundtrips_sync(self):
        import json
        chat = self.db.create_chat('Время ответа')
        self.db.add_message(chat, 'ai', 'Готово', elapsed_seconds=12.75)
        for invalid in (-1, float('nan'), float('inf')):
            with self.assertRaises(RuntimeError):
                self.db.add_message(chat, 'ai', 'Не сохранять', elapsed_seconds=invalid)
        self.assertEqual(len(self.db.get_messages(chat)), 1)
        self.close()
        self.db = advanced_xopilot.PyDatabase(str(self.path))
        self.assertEqual(self.db.get_messages(chat)[0].elapsed_seconds, 12.75)
        snapshot = self.db.sync_chat_snapshot(chat)
        clone = self.db.apply_sync_chat(None, None, snapshot, 'receipt', '{}')
        self.assertEqual(self.db.get_messages(clone)[0].elapsed_seconds, 12.75)
        old = json.loads(snapshot)
        old['messages'][0].pop('elapsed_seconds')
        legacy = self.db.apply_sync_chat(None, None, json.dumps(old), 'receipt', '{}')
        self.assertIsNone(self.db.get_messages(legacy)[0].elapsed_seconds)

    def test_v2_migration_preserves_existing_messages(self):
        import shutil
        import subprocess
        if not shutil.which('sqlcipher'):self.skipTest('SQLCipher CLI for old schema fixture')
        path=Path(self.directory.name)/'v2.db';key='31'*32
        with advanced_xopilot.PyDatabase(str(path),key=key) as source:
            chat=source.create_chat('Старый чат')
            source.add_message(chat,'ai','Существующий ответ')
        subprocess.run(['sqlcipher',str(path)],input="PRAGMA key='"+key+"';\nALTER TABLE messages DROP COLUMN elapsed_seconds;\nPRAGMA user_version=2;\n",
                       text=True,capture_output=True,check=True)
        with advanced_xopilot.PyDatabase(str(path),key=key) as reopened:
            message=reopened.get_messages(chat)[0]
            self.assertEqual(message.content,'Существующий ответ')
            self.assertIsNone(message.elapsed_seconds)
            self.assertEqual(reopened.schema_version(),3)

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

    def test_sync_import_cas_receipt_and_new_id_are_atomic(self):
        import json
        chat=self.db.create_chat('Before')
        message=self.db.add_message(chat,'user','Original')
        snapshot=self.db.sync_chat_snapshot(chat)
        self.db.update_message(message,'Local edit during download')
        payload=json.loads(snapshot);payload['messages'][0]['content']='Remote edit'
        ledger={'records':{'chat:qa':{'local_id':chat}},'applying':'chat:qa'}
        self.assertIsNone(self.db.apply_sync_chat(chat,snapshot,json.dumps(payload),'sync_qa',json.dumps(ledger)))
        self.assertEqual(self.db.get_messages(chat)[0].content,'Local edit during download')
        self.assertIsNone(self.db.get_setting('sync_qa'))
        ledger['records']['chat:qa']['local_id']=None
        created=self.db.apply_sync_chat(None,None,json.dumps(payload),'sync_qa',json.dumps(ledger))
        saved=json.loads(self.db.get_setting('sync_qa'))
        self.assertEqual(saved['records']['chat:qa']['local_id'],created)
        self.assertNotIn('applying',saved)
        self.assertEqual(self.db.get_messages(created)[0].content,'Remote edit')

    def test_sync_settings_cas_never_overwrites_concurrent_project_edit(self):
        self.db.set_setting('workspace_qa','edited locally')
        self.assertFalse(self.db.apply_sync_settings([('workspace_qa','original')],[('workspace_qa','remote'),('receipt_qa','done')]))
        self.assertEqual(self.db.get_setting('workspace_qa'),'edited locally')
        self.assertIsNone(self.db.get_setting('receipt_qa'))

    def test_explicit_close_releases_file_despite_retained_callbacks(self):
        alias = self.db
        self.db.close()
        self.db.close()
        with self.assertRaisesRegex(RuntimeError, 'закрыта'):
            alias.get_setting('missing')
        moved = self.path.with_suffix('.moved')
        self.path.rename(moved)
        with advanced_xopilot.PyDatabase(str(moved)) as reopened:
            self.assertEqual(reopened.list_chats(), [])
        with self.assertRaisesRegex(RuntimeError, 'закрыта'):
            reopened.list_chats()
