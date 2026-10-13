"""Real encrypted persistence, memory isolation/CAS and bounded file workflows."""
import io
import asyncio
import json
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from PIL import Image
import flet as ft
from App.services import profile, user_memory as memory, material_preview as preview
from App.services import storage, material_store, mobile_documents, navigation, sync_files
from App.services.db import advanced_xopilot
from App.services.sync_entities import Entities
from App.services.cloud_sync import fingerprint
from App.services.sync_files import Files
from App.settings.memory import build_memory_page


@unittest.skipIf(advanced_xopilot is None, 'Build native DB')
class PersonalMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name);self.path = self.root/'test.db'
        self.db = advanced_xopilot.PyDatabase(str(self.path))
        self.addCleanup(lambda: setattr(self, 'db', None))
        for module in (profile, memory, preview, storage):
            patcher = patch.object(module, 'get_db', side_effect=lambda: self.db)
            patcher.start();self.addCleanup(patcher.stop)
        for module in (preview, storage, material_store, sync_files):
            patcher = patch.object(module, 'app_data_dir', return_value=self.root)
            patcher.start();self.addCleanup(patcher.stop)

    def test_saved_edited_deleted_notes_survive_reopen_without_plaintext_database(self):
        identifier = memory.save('Я предпочитаю короткие ответы о Python QA_MEMORY_715')
        profile.update(name='Денис')
        self.db = None;self.db = advanced_xopilot.PyDatabase(str(self.path))
        self.assertIn('QA_MEMORY_715', memory.context('Python'))
        self.assertEqual(profile.read()['name'], 'Денис')
        memory.save('Я изучаю Rust QA_MEMORY_716', identifier)
        self.assertNotIn('QA_MEMORY_715', memory.context('Python'))
        self.assertIn('QA_MEMORY_716', memory.context('Rust'))
        self.assertNotIn(b'QA_MEMORY_716', self.path.read_bytes())
        memory.delete(identifier);self.assertEqual(memory.read()['items'], [])

    def test_exact_user_quotes_only_and_no_credentials_attachments_or_private_reads(self):
        generator = Mock(return_value=json.dumps({'quotes': ['Я пишу на Python.', 'Я космонавт.', 'Как решить задачу?', 5]}))
        self.assertEqual(memory.capture('Я пишу на Python. Как решить задачу?', generator), ['Я пишу на Python.'])
        self.assertEqual(memory.capture('Я пишу на Python.', generator), [])
        generator.reset_mock()
        self.assertEqual(memory.capture('Мой API-ключ: sk-qa-secret', generator), [])
        self.assertEqual(memory.capture('Я пишу на Rust.', generator, private=True), [])
        self.assertEqual(memory.capture('Реши 23 + 19', generator), [])
        generator.assert_not_called()
        with self.assertRaises(ValueError):memory.save('password: secret')

    def test_name_assertion_replaces_old_name_and_questions_never_become_memory(self):
        generator=Mock(side_effect=AssertionError('Name assertion requires no inference'))
        self.assertEqual(memory.capture('Меня зовут Денис.',generator),['Имя пользователя: Денис'])
        self.assertEqual(memory.capture('Как меня зовут?',generator),[])
        self.assertEqual(memory.capture('My name is Alex.',generator),['Имя пользователя: Alex'])
        self.db=None;self.db=advanced_xopilot.PyDatabase(str(self.path))
        self.assertEqual([item['text'] for item in memory.read()['items']],['Имя пользователя: Alex'])
        self.assertNotIn(b'Alex',self.path.read_bytes())
        generator.assert_not_called()

    def test_clear_all_history_deletes_chats_and_drafts_but_keeps_project_memory_and_canvas(self):
        from App.services import chat_store,workspaces,canvases
        with patch.object(chat_store,'get_db',return_value=self.db),patch.object(workspaces,'get_db',return_value=self.db),\
             patch.object(canvases,'get_db',return_value=self.db),patch.object(chat_store,'_active_chat_id',None):
            wid=workspaces.create_workspace('Keep project')['id']
            for title in ('First','Second'):
                cid=self.db.create_chat(title);self.db.add_message(cid,'user','Own QA message')
                self.db.set_setting('draft:'+str(cid),json.dumps({'text':'draft'}))
                workspaces.assign_chat(cid,wid);canvases.create_document(title='QA',chat_id=cid)
            identifiers=[row[0] for row in self.db.list_chats()]
            memory.save('Я изучаю Python')
            self.assertEqual(chat_store.clear_all_chats(),2)
            self.assertTrue(all(self.db.get_setting('draft:'+str(cid))=='' for cid in identifiers))
            self.assertEqual(self.db.list_chats(),[])
            self.assertEqual(len(canvases.list_documents()),2)
            self.assertEqual(workspaces.list_workspaces()[1]['id'],wid)
            self.assertEqual(len(memory.read()['items']),1)

    def test_explicit_capture_no_extra_inference_and_disable_clear_wins_over_pending_extraction(self):
        generator = Mock(side_effect=AssertionError('No inference for explicit memory'))
        self.assertEqual(memory.capture('Запомни: Я предпочитаю Rust', generator), ['Я предпочитаю Rust'])
        def delayed(*args, **kwargs):
            memory.clear()
            return json.dumps({'quotes': ['Я пишу на Python']})
        self.assertEqual(memory.capture('Я пишу на Python', delayed), [])
        self.assertEqual(memory.read()['items'], [])
        memory.configure(enabled=False)
        memory.capture('Я изучаю Rust', generator)
        self.assertEqual(memory.context('Rust'), '')
        generator.assert_not_called()

    def test_profile_cloud_import_keeps_memory_and_google_refresh_preserves_it(self):
        owner = str(uuid.uuid4());key = 'profile:'+str(uuid.uuid5(uuid.UUID(owner), 'Xopilot/profile/v1'))
        payload = {'name': 'Облачное имя', 'avatar': '', 'memory': {'enabled': True, 'automatic': False,
            'items': [{'id': str(uuid.uuid4()), 'text': 'Я предпочитаю Python', 'updated': 1, 'automatic': False}]}}
        entities = object.__new__(Entities);entities.db = self.db;entities.owner = owner
        entities.ledger = {'records': {}};entities.save = Mock()
        record = dict(scope='profile', kind='profile', revision=0, local_id=None, hash=None)
        entities.ledger['records'][key] = record
        change = dict(revision=1, deleted=False)
        self.assertTrue(entities._apply(key, record, change, payload, None))
        self.assertEqual(record['hash'], fingerprint(payload))
        self.assertIn('Python', memory.context())
        profile.import_google(owner, name='Google name')
        self.assertIn('Python', memory.context())
        self.assertFalse(memory.read()['automatic'])

    def test_two_encrypted_databases_transfer_and_delete_memory_with_real_e2ee_codec(self):
        owner=str(uuid.uuid4());secret=b'k'*32
        identifier=memory.save('Я изучаю Rust QA_ENCRYPTED_MEMORY_715')
        ledger={'records':{},'blobs':{},'conflicts':{}}
        files=Files(owner,secret,ledger,lambda:None)
        options={key:False for key in ('profile','chats','workspaces','canvases','protected','materials')}
        options['profile']=True
        sender=object.__new__(Entities);sender.db=self.db;sender.owner=owner;sender.ledger=ledger
        sender.options=options;sender.files=files;sender.save=lambda:None
        key,snapshot=next(sender.snapshots())
        envelope=files.encode(key,'profile',snapshot['payload'])
        self.assertNotIn('QA_ENCRYPTED_MEMORY_715',json.dumps(envelope))
        receiver=object.__new__(Entities);receiver.owner=owner;receiver.ledger={'records':{},'conflicts':{}}
        receiver.save=lambda:None;receiver.db=advanced_xopilot.PyDatabase(str(self.root/'receiver.db'))
        self.addCleanup(lambda:setattr(receiver,'db',None))
        change={'kind':'profile','revision':1,'deleted':False,'data':envelope}
        receiver.receive(key,change,files.decode(key,envelope))
        self.assertEqual(memory.read(receiver.db)['items'][0]['id'],identifier)
        memory.delete(identifier)
        key,snapshot=next(sender.snapshots());envelope=files.encode(key,'profile',snapshot['payload'])
        change.update(revision=2,data=envelope)
        receiver.receive(key,change,files.decode(key,envelope))
        self.assertEqual(memory.read(receiver.db)['items'],[])
        self.assertFalse(receiver.ledger['conflicts'])

    def test_bounded_preview_real_streamed_export_and_trash_preview(self):
        source = self.root/'source.txt';source.write_bytes(b'QA_FILE_715\n'+b'a'*200000)
        path = material_store.store_material('large.txt', path=str(source))
        result = preview.preview(path, 'large.txt')
        self.assertTrue(result['truncated']);self.assertLessEqual(len(result['text']), preview.TEXT_PREVIEW_BYTES)
        with tempfile.TemporaryDirectory() as export_root:
            target = Path(export_root)/'copy.txt';preview.copy_to(path, target)
            self.assertEqual(target.read_bytes(), source.read_bytes())
        with self.assertRaises(ValueError):preview.copy_to(path, self.root/'xopilot.db')
        with self.assertRaises(ValueError):preview.preview(source, 'source.txt')
        identifier = storage.trash_material(path)
        self.assertIn('QA_FILE_715', preview.preview(self.root/'material-trash'/identifier, 'large.txt')['text'])
        storage.restore_material(identifier);self.assertTrue(Path(path).exists());self.assertTrue(source.exists())
        image_path = material_store.store_material('image.png', data=self.image())
        self.assertTrue(preview.preview(image_path, 'image.png')['image'].startswith('data:image/jpeg;base64,'))

    def image(self):
        output = io.BytesIO();Image.new('RGB',(200,100),'#123456').save(output,'PNG');return output.getvalue()

    def test_memory_interface_uses_real_edit_delete_search(self):
        page = Mock();identifier = memory.save('Я пишу на Python')
        content = build_memory_page(page)
        rows = content.controls[-1]
        row = rows.controls[0].content.controls[-1]
        row.controls[-2].on_click(None)
        dialog = page.show_dialog.call_args.args[0]
        dialog.content.controls[0].value = 'Я изучаю Rust'
        dialog.actions[-1].on_click(None)
        self.assertEqual(memory.read()['items'][0]['id'], identifier)
        self.assertIn('Rust', memory.context())
        rows.controls[0].content.controls[-1].controls[-1].on_click(None)
        self.assertEqual(memory.read()['items'], [])


class MemoryCaptureLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_private_transition_cancels_capture_and_releases_busy_state(self):
        from App.app.memory_capture import MemoryCapture
        entered, release = threading.Event(), threading.Event()
        tasks = []
        page = Mock()
        page.run_task.side_effect = lambda fn: tasks.append(asyncio.create_task(fn())) or tasks[-1]
        capture = MemoryCapture(page)
        def extract(*args, **kwargs):
            entered.set()
            release.wait(2)
            self.assertTrue(kwargs['cancelled'].is_set())
            return []
        with patch('App.app.memory_capture.user_memory.capture', side_effect=extract):
            capture.submit('Remember QA', Mock())
            await asyncio.to_thread(entered.wait, 2)
            self.assertTrue(capture.busy)
            capture.submit('private QA', Mock(), private=True)
            self.assertTrue(capture.busy)
            release.set()
            await asyncio.gather(*tasks)
            self.assertFalse(capture.busy)
            page.show_dialog.assert_not_called()


class StreamedAndroidExportTests(unittest.IsolatedAsyncioTestCase):
    async def test_export_existing_file_passes_only_path_to_native_service(self):
        bridge = AsyncMock(side_effect=['export-token', {'token':'export-token', 'tag':'export',
            'state':'ready','exported':True}, None])
        with patch.object(mobile_documents,'call_async',bridge), patch.object(Path,'read_bytes',side_effect=AssertionError('No whole-file buffers')):
            self.assertTrue(await mobile_documents.save_document_file('large.mp4', '/private/large.mp4'))
        self.assertEqual(bridge.await_args_list[0].args, ('stageExport', {'path':'/private/large.mp4','name':'large.mp4'}))


class StorageInterfaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_storage_menu_preview_export_and_search_use_real_material_identifiers(self):
        from App.settings.account import storage as ui
        page = Mock(width=400, height=800, web=False)
        page._dialogs.controls = []
        tasks = []
        page.run_task.side_effect = lambda f,*args: tasks.append((f,args))
        inventory = {key:0 for key in ('db_bytes','materials_bytes','private_bytes','cache_bytes','trash_bytes','recovery_bytes','models_bytes')}
        inventory.update(files=[dict(path='/owned/memo.txt',name='memo.txt',bytes=20,references=['Чат: QA'])],trash={},removed={})
        with patch.object(ui.storage,'local_inventory',return_value=inventory),patch.object(ui.storage,'private_recoveries',return_value=[]), \
             patch.object(ui.profile,'recoveries',return_value=[]),patch.object(ui.cloud_account,'state',return_value=None), \
             patch.object(ui.navigation,'save'),patch.object(ui,'open_material',AsyncMock()) as show,patch.object(ui.Path,'is_file',return_value=True):
            ui.open_storage(page)
            dialog = page.show_dialog.call_args.args[0];dialog.open = True;page._dialogs.controls = [dialog]
            # Search invokes the real renderer without running its periodic task.
            self.assertIsInstance(dialog.content.controls[1], ft.Column)
            search = dialog.content.controls[1].controls[0]
            self.assertFalse(search.expand)  # A flex child inside Wrap cannot render on Flutter.
            await search.on_change(None)
            content = dialog.content.controls[2]
            material_card = next(row for row in content.controls if isinstance(row,ft.Container))
            menu = material_card.content.controls[-1]
            menu.items[0].on_click(None)
            fn,args = tasks[-1];await fn(*args)
            show.assert_awaited_once_with(page,'/owned/memo.txt','memo.txt',references=['Чат: QA'])
            search.value = 'missing';await search.on_change(None)
            self.assertFalse(any(isinstance(row,ft.Container) for row in content.controls))
