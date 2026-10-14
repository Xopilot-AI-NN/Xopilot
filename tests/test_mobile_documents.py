import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from App.services import mobile_documents as documents, material_store


class DocumentRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_avatar_does_not_block_future_file_selection(self):
        from App.services import profile
        operation={'token':'invalid-avatar','state':'ready','tag':'avatar',
                   'files':[{'name':'broken.jpg','path':'/native/invalid'}]}
        with patch.object(profile,'set_avatar',side_effect=ValueError('invalid image')), \
             patch.object(documents,'call_async',AsyncMock()) as bridge:
            with self.assertRaisesRegex(ValueError,'invalid image'):
                await documents.import_selection(operation)
        bridge.assert_awaited_once_with('ackDocuments',{'token':'invalid-avatar'})
    async def test_workspace_selection_survives_restart_and_keeps_logical_names(self):
        from App.services import library, workspaces
        identifier = 'a'*32
        operation = {'token':'workspace-token','state':'ready','tag':'workspace:'+identifier,
            'files':[{'name':'source.txt','path':'/native/selected'}]}
        with patch.object(workspaces,'list_workspaces',return_value=[{'id':identifier}]), \
             patch.object(documents,'store_material',return_value='/managed/source.txt'), \
             patch.object(library,'append_materials') as append,patch.object(documents,'call_async',AsyncMock()) as bridge:
            result = await documents.import_selection(operation)
        append.assert_called_once_with(identifier,[{'name':'source.txt','path':'/managed/source.txt','enabled':True}])
        bridge.assert_awaited_once_with('ackDocuments',{'token':'workspace-token'})
        self.assertEqual(result['workspace_id'],identifier)

    async def test_avatar_write_failure_retains_native_image_for_retry(self):
        from App.services import profile
        operation = {'token':'avatar-token','state':'ready','tag':'avatar',
            'files':[{'name':'photo.jpg','path':'/native/photo'}]}
        with patch.object(profile,'set_avatar',side_effect=RuntimeError('disk full')), \
             patch.object(documents,'call_async',AsyncMock()) as bridge:
            with self.assertRaisesRegex(RuntimeError,'disk full'):
                await documents.import_selection(operation)
            bridge.assert_not_awaited()

    async def test_export_bytes_are_staged_before_opening_picker_and_recovered_after_restart(self):
        with TemporaryDirectory() as directory:
            staged = []
            async def bridge(method, args=None):
                if method == 'pendingDocuments':
                    return None
                if method == 'stageExport':
                    self.assertEqual(Path(args['path']).read_bytes(), b'export bytes')
                    staged.append(args['path'])
                    return 'export-token'
                if method == 'exportDocument':
                    self.assertFalse(Path(staged[0]).exists())
                    return {'token': 'export-token', 'tag': 'export', 'state': 'ready', 'exported': True}
                self.assertEqual(method, 'ackDocuments')
            with patch.object(documents, 'app_data_dir', return_value=Path(directory)), \
                 patch.object(documents, 'call_async', side_effect=bridge):
                self.assertTrue(await documents.save_document('canvas.md', b'export bytes'))
                self.assertEqual(await documents.import_selection({'token': 'export-token', 'tag': 'export',
                    'state': 'ready', 'exported': True}), {'exported': True})

    async def test_result_after_process_death_is_saved_once_and_acknowledged_after_db(self):
        with TemporaryDirectory() as directory:
            source = Path(directory)/'picked'
            source.write_text('real file bytes')
            draft = {'text': 'Keep my draft', 'files': []}
            writes = []
            def save(chat_id, text, files):
                draft.update(text=text, files=files)
                writes.append(chat_id)
            async def bridge(method, args=None):
                self.assertEqual(method, 'ackDocuments')
                self.assertTrue(writes)
            operation = {'token': 'test-token', 'tag': 'chat:7', 'state': 'ready',
                         'files': [{'name': 'memo.txt', 'path': str(source)}]}
            with patch.object(documents, 'get_db', return_value=Mock(list_chats=Mock(return_value=[(7, 'Chat', 0)]))), \
                 patch.object(documents, 'read_draft', side_effect=lambda _: dict(draft)), \
                 patch.object(documents, 'write_draft', side_effect=save), \
                 patch.object(documents, 'call_async', side_effect=bridge), \
                 patch.object(material_store, 'app_data_dir', return_value=Path(directory)/'app'):
                result = await documents.import_selection(operation)
                await documents.import_selection(operation)  # Restart before native ack.
            self.assertEqual(result['chat_id'], 7)
            self.assertEqual(draft['text'], 'Keep my draft')
            self.assertEqual(len(draft['files']), 1)
            self.assertEqual(Path(draft['files'][0]).read_text(), 'real file bytes')

    async def test_deleted_or_private_destination_is_discarded_without_redirect(self):
        for tag in ('chat:77', 'chat:-1', 'library:anything'):
            bridge = AsyncMock()
            with patch.object(documents, 'call_async', bridge), \
                 patch.object(documents, 'get_db', return_value=Mock(list_chats=Mock(return_value=[(7, 'Other chat', 0)]))), \
                 patch.object(documents, 'store_material') as store, patch.object(documents, 'write_draft') as write:
                result = await documents.import_selection({'token': 'test', 'state': 'ready', 'tag': tag, 'files': [{'path': '/unused'}]})
            self.assertIsNone(result)
            bridge.assert_awaited_once_with('ackDocuments', {'token': 'test'})
            store.assert_not_called()
            write.assert_not_called()

    async def test_failed_db_write_keeps_native_result_for_retry(self):
        bridge = AsyncMock()
        with patch.object(documents, 'call_async', bridge), \
             patch.object(documents, 'get_db', return_value=Mock(list_chats=Mock(return_value=[(7, 'Chat', 0)]))), \
             patch.object(documents, 'read_draft', return_value={'text': 'draft', 'files': []}), \
             patch.object(documents, 'store_material', return_value='/managed/file'), \
             patch.object(documents, 'write_draft', side_effect=RuntimeError('disk full')):
            with self.assertRaisesRegex(RuntimeError, 'disk full'):
                await documents.import_selection({'token': 'test', 'tag': 'chat:7', 'state': 'ready',
                                                  'files': [{'name': 'memo.txt', 'path': '/native/file'}]})
        bridge.assert_not_awaited()

    async def test_startup_waits_for_native_copy_result(self):
        operation = {'token': 'test', 'state': 'ready'}
        with patch.object(documents, 'call_async', AsyncMock(side_effect=[{'state': 'copying'}, operation])), \
             patch.object(documents, 'import_selection', AsyncMock(return_value={'chat_id': 7})) as finish, \
             patch.object(documents.asyncio, 'sleep', AsyncMock()):
            self.assertEqual(await documents.recover_pending_documents(), {'chat_id': 7})
            finish.assert_awaited_once_with(operation)

    async def test_new_picker_recovers_previous_ready_files_and_returns_merged_draft(self):
        draft = {'text': 'Keep typed text', 'files': ['/managed/existing']}
        old = {'token': 'old', 'tag': 'chat:7', 'state': 'ready',
               'files': [{'name': 'old.txt', 'path': '/native/old'}]}
        new = {'token': 'new', 'tag': 'chat:7', 'state': 'ready',
               'files': [{'name': 'new.txt', 'path': '/native/new'}]}
        async def bridge(method, args=None):
            if method == 'pendingDocuments': return old
            if method == 'pickDocuments':
                self.assertIn('/managed/old', draft['files'])
                return new
            self.assertEqual(method, 'ackDocuments')
        def write(chat, text, files): draft.update(text=text, files=files)
        with patch.object(documents, 'call_async', side_effect=bridge), \
             patch.object(documents, 'get_db', return_value=Mock(list_chats=Mock(return_value=[(7, 'Chat', 0)]))), \
             patch.object(documents, 'read_draft', side_effect=lambda _: dict(draft)), \
             patch.object(documents, 'write_draft', side_effect=write), \
             patch.object(documents, 'store_material', side_effect=lambda name, **_: '/managed/' + name.split('.')[0]):
            result = await documents.pick_chat_documents(7)
        self.assertEqual(result['files'], ['/managed/existing', '/managed/old', '/managed/new'])
        self.assertEqual(draft['text'], 'Keep typed text')

    async def test_python_does_not_discard_waiting_native_operation(self):
        with patch.object(documents, 'call_async', AsyncMock(return_value={'state': 'waiting', 'token': 'old'})) as bridge:
            await documents._recover_before_new_operation()
        bridge.assert_awaited_once_with('pendingDocuments')
