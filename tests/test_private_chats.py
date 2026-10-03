"""Private persistence, password and lifecycle guarantees using real crypto/files."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from App.services.private_chats import PrivateChatSession, PrivateCanvasStore, LockedChatError


class PrivateChatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'sealed'
        self.session = PrivateChatSession(self.root)
        self.addCleanup(self.session.close_all)
        self.password = 'local-test-password'

    def test_password_isolates_transcript_draft_canvas_and_attachment(self):
        cid = self.session.create(self.password)
        original = Path(self.temp.name) / 'source.txt'
        original.write_text('PRIVATE_ATTACHMENT_631')
        path = self.session.store_material(cid, 'source.txt', path=original)
        self.session.add_message(cid, 'user', 'PRIVATE_QUESTION_631', attachments=[('source.txt', path)])
        self.session.draft(cid, 'PRIVATE_DRAFT_631', [path])
        doc = PrivateCanvasStore(self.session, cid).create_document(content='PRIVATE_CANVAS_631')
        self.session.rename(cid, 'PRIVATE_TITLE_631')
        for file in self.root.rglob('*'):
            if file.is_file():
                self.assertNotIn(b'PRIVATE_', file.read_bytes())
                self.assertNotIn(self.password.encode(), file.read_bytes())
        self.session.close(cid)
        self.assertFalse(Path(path).exists())
        self.assertEqual(self.session.items()[0][1], 'Защищённый анонимный чат')
        with self.assertRaises(LockedChatError):
            self.session.unlock(cid, 'incorrect-password')
        with self.assertRaises(LockedChatError):
            self.session.messages(cid)
        self.session.unlock(cid, self.password)
        self.assertEqual(self.session.messages(cid)[0].content, 'PRIVATE_QUESTION_631')
        recovered = Path(self.session.messages(cid)[0].attachments[0][1])
        self.assertEqual(recovered.read_text(), 'PRIVATE_ATTACHMENT_631')
        self.assertEqual(self.session.draft(cid)['text'], 'PRIVATE_DRAFT_631')
        self.assertEqual(PrivateCanvasStore(self.session, cid).get_document(doc['id'])['content'], 'PRIVATE_CANVAS_631')
        self.session.delete(cid)
        self.assertTrue(original.exists())
        self.assertEqual(list(self.root.rglob('*.sealed')), [])

    def test_temporary_state_disappears_on_close_without_persistent_files(self):
        cid = self.session.create(self.password, temporary=True)
        file = self.session.store_material(cid, 'temporary.txt', data=b'TEMP_MATERIAL')
        self.session.add_message(cid, 'user', 'TEMP_QUESTION', attachments=[('temporary.txt', file)])
        self.session.draft(cid, 'TEMP_DRAFT', [file])
        PrivateCanvasStore(self.session, cid).create_document(content='TEMP_CANVAS')
        self.assertFalse(self.root.exists())
        self.session.close(cid)
        self.assertFalse(Path(file).exists())
        self.assertEqual(self.session.items(), [])
        self.assertFalse(self.root.exists())

    def test_other_window_cannot_overwrite_unlocked_chat(self):
        cid = self.session.create(self.password)
        other = PrivateChatSession(self.root)
        self.addCleanup(other.close_all)
        with self.assertRaisesRegex(LockedChatError, 'другом окне'):
            other.unlock(cid, self.password)
        self.session.add_message(cid, 'user', 'saved')
        self.session.close(cid)
        other.unlock(cid, self.password)
        self.assertEqual(other.messages(cid)[0].content, 'saved')

    def test_authenticated_ciphertext_rejects_tampering(self):
        cid = self.session.create(self.password)
        self.session.close(cid)
        envelope = json.loads(self.session._path(cid).read_text())
        import base64
        cipher = bytearray(base64.b64decode(envelope['ciphertext']))
        cipher[0] ^= 1
        envelope['ciphertext'] = base64.b64encode(cipher).decode()
        self.session._path(cid).write_text(json.dumps(envelope))
        with self.assertRaises(LockedChatError):
            self.session.unlock(cid, self.password)
        self.assertFalse(self.session.opened(cid))

    def test_attachment_failure_removes_all_decrypted_scratch_files(self):
        cid = self.session.create(self.password)
        self.session.store_material(cid, 'one.txt', data=b'FIRST_PRIVATE')
        self.session.store_material(cid, 'two.txt', data=b'SECOND_PRIVATE')
        assets = list(self.session._state(cid)['data']['files'])
        self.session.close(cid)
        corrupted = self.session._path(cid).parent / (assets[1]+'.sealed')
        corrupted.write_bytes(b'corrupt')
        with self.assertRaises(LockedChatError):
            self.session.unlock(cid, self.password)
        folder = Path(self.session._scratch.name) / f'{abs(cid):x}'
        self.assertFalse(folder.exists())

    def test_failed_write_rolls_back_visible_state_and_partial_attachment(self):
        cid = self.session.create(self.password)
        mid = self.session.add_message(cid, 'user', 'original')
        with patch('App.services.private_chats._atomic', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.session.edit_message(mid, 'unsaved')
            self.assertEqual(self.session.messages(cid)[0].content, 'original')
            with self.assertRaises(OSError):
                self.session.store_material(cid, 'unsaved.txt', data=b'PRIVATE')
        self.assertEqual(self.session._state(cid)['data']['files'], {})
        self.assertEqual(len(list(self.session._path(cid).parent.glob('*.sealed'))), 1)

    def test_regular_material_cannot_be_attached_without_private_copy(self):
        cid = self.session.create(self.password)
        with self.assertRaises(ValueError):
            self.session.add_message(cid, 'user', 'x', attachments=[('outside.txt', '/outside.txt')])
        self.assertEqual(self.session.messages(cid), [])

    def test_malformed_directory_does_not_break_chat_listing(self):
        self.root.mkdir()
        folder = self.root / 'invalid-chat'
        folder.mkdir()
        (folder/'chat.sealed').write_text('junk')
        self.assertEqual(self.session.items(), [])

    def test_crashed_scratch_is_reclaimed_but_live_session_is_preserved(self):
        live_cid = self.session.create(self.password, temporary=True)
        path = self.session.store_material(live_cid, 'live.txt', data=b'live')
        abandoned = Path(tempfile.mkdtemp(prefix='xopilot-private-'))
        self.addCleanup(lambda: __import__('shutil').rmtree(abandoned, ignore_errors=True))
        (abandoned/'.owner.lock').touch()
        (abandoned/'lost.txt').write_text('private')
        other = PrivateChatSession(self.root)
        self.addCleanup(other.close_all)
        self.assertFalse(abandoned.exists())
        self.assertTrue(Path(path).exists())

    def test_lease_releases_when_ui_thread_differs_from_unlock_thread(self):
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            cid = pool.submit(self.session.create, self.password).result()
        self.session.close(cid)
        other = PrivateChatSession(self.root)
        self.addCleanup(other.close_all)
        other.unlock(cid, self.password)
        self.assertTrue(other.opened(cid))


import test_real_answers
from App.app import main as main_ui
from App.services import api_chat


class PrivateUITests(test_real_answers.PersistenceUITests):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.private = PrivateChatSession(Path(self.temp.name)/'protected')
        self.addCleanup(self.private.close_all)
        patcher = patch('App.services.private_chats.PrivateChatSession', return_value=self.private)
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()

    def switch(self, cid):
        with patch.object(main_ui, 'build_chats_dialog') as dialog:
            self.menu.call_args.kwargs['on_chats_click'](None)
            dialog.call_args.kwargs['on_select_chat'](cid)

    async def test_private_request_ignores_api_workspace_and_global_agent(self):
        cid = self.private.create('ui-test-password')
        self.switch(cid)
        main_ui.write_draft.reset_mock()
        self.prompt.value = 'private question'
        with patch.object(api_chat, 'is_api_selected', return_value=True), patch.object(api_chat, 'generate_reply') as api, patch.object(main_ui.workspaces, 'chat_resources') as resources:
            await self.send(None)
        api.assert_not_called()
        resources.assert_not_called()
        self.generate.assert_called_once()
        self.assertTrue(self.generate.call_args.kwargs['private'])
        self.assertEqual(self.generate.call_args.kwargs['history'], [])
        self.assertEqual([m.content for m in self.private.messages(cid)], ['private question', 'Ответ'])
        self.save.assert_not_called()
        self.save_ai.assert_not_called()
        main_ui.write_draft.assert_not_called()

    async def test_leaving_private_chat_erases_temporary_and_locks_saved(self):
        cid = self.private.create('ui-test-password', temporary=True)
        self.switch(cid)
        self.prompt.value = 'temporary draft'
        self.switch(1)
        self.assertFalse(self.private.opened(cid))
        self.assertEqual(self.private.items(), [])
        self.assertEqual(self.prompt.value, '')
        cid = self.private.create('ui-test-password')
        self.switch(cid)
        self.prompt.value = 'protected draft'
        self.switch(1)
        self.assertFalse(self.private.opened(cid))
        self.private.unlock(cid, 'ui-test-password')
        self.switch(cid)
        self.assertEqual(self.prompt.value, 'protected draft')

    async def test_late_answer_after_disconnect_cannot_leak_into_normal_retry(self):
        import asyncio
        import threading
        from concurrent.futures import CancelledError
        cid = self.private.create('ui-test-password')
        self.switch(cid)
        entered, release = threading.Event(), threading.Event()
        def generate(*a, **kw):
            entered.set()
            release.wait(3)
            raise CancelledError()
        self.generate.side_effect = generate
        self.prompt.value = 'private interrupted question'
        task = asyncio.create_task(self.send(None))
        try:
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            await self.page.on_disconnect(None)
            self.assertEqual(self.prompt.value, '')
            self.assertFalse(self.private.opened(cid))
        finally:
            release.set()
            await task
        before = self.generate.call_count
        await self.send(None, retry=True)
        self.assertEqual(self.generate.call_count, before)
        self.save.assert_not_called()


class PrivateGenerationTests(unittest.TestCase):
    def test_private_reply_forces_fresh_context_and_does_not_record_profile_stats(self):
        from unittest.mock import Mock
        from App.services import llm
        response = Mock()
        response.send_message.return_value = {'content': [{'text': 'local reply'}]}
        context = Mock(__enter__=Mock(return_value=response), __exit__=Mock(return_value=False))
        engine = Mock()
        engine.create_conversation.return_value = context
        shared = Mock()
        with patch.multiple(llm, _engine=engine, _conversation=shared), patch.object(llm, 'record_generation') as stats, patch.object(llm, 'response_language_instruction') as language:
            self.assertEqual(llm.generate_reply('private', private=True, instructions='ordinary workspace secret'), 'local reply')
        shared.send_message.assert_not_called()
        stats.assert_not_called()
        language.assert_not_called()
        self.assertEqual(engine.create_conversation.call_args.kwargs['messages'], [])
        self.assertNotIn('ordinary workspace secret', engine.create_conversation.call_args.kwargs['system_message'])
