"""Real API + SQLCipher + two profiles. Explicit isolated PostgreSQL is required."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import uuid
from unittest.mock import patch
from App.services import cloud_account as cloud, cloud_sync as sync, cloud_traffic as traffic
from App.services import sync_entities, sync_files, profile, workspaces, library, material_store
from App.services.db import advanced_xopilot

@unittest.skipUnless(os.environ.get('XOPILOT_TEST_DATABASE_URL'),'requires isolated PostgreSQL integration environment')
class SyncIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='xopilot-sync-qa-')
        cls.root=Path(cls.temp.name)
        os.chmod(cls.root,0o700)
        env={**os.environ,'XOPILOT_QA_ROOT':str(cls.root)}
        cls.server=subprocess.Popen(['/home/developer/Xopiser/xopilot-backend/target/debug/examples/qa_server'],env=env,stdout=subprocess.PIPE,text=True)
        cls.endpoint=cls.server.stdout.readline().strip()
        if not cls.endpoint.startswith('http://127.0.0.1:'):raise RuntimeError('QA server failed')
        cls.email='qa_'+uuid.uuid4().hex+'@example.invalid'
        cls.password='Synthetic account password 2026!'
        pending=cloud._request(cls.endpoint,'/auth/register',method='POST',body={'username':'QA','email':cls.email,'password':cls.password})
        code=(cls.root/'mail'/hashlib.sha256(cls.email.encode()).hexdigest()).read_text()
        cls.tokens=cloud._request(cls.endpoint,'/auth/verify-email',method='POST',body={'registration_id':pending['registration_id'],'code':code})
        cls.owner=cls.tokens['account_id']

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate();cls.server.wait(timeout=15);cls.server.stdout.close();cls.temp.cleanup()

    def profile(self,name):
        root=self.root/name;root.mkdir(exist_ok=True)
        db=advanced_xopilot.PyDatabase(str(root/'xopilot.db'))
        return root,db

    def bind(self,root,db):
        from contextlib import ExitStack
        stack=ExitStack()
        for module in (cloud,sync,traffic,sync_entities,profile,workspaces):stack.enter_context(patch.object(module,'get_db',return_value=db))
        for module in (sync,sync_entities,sync_files,material_store):stack.enter_context(patch.object(module,'app_data_dir',return_value=root))
        return stack

    def login(self):
        cloud.sign_in(self.email,self.password,endpoint=self.endpoint)
        sync.setup('Synthetic sync password 2026!')
        sync.save_options({'enabled':True,'auto':False})

    def test_busy_replica_uploads_completed_messages_without_importing_remote_context(self):
        self.new_account()
        ar,a=self.profile('busy-a');br,b=self.profile('busy-b');cr,c=self.profile('busy-c')
        title='Busy replica '+uuid.uuid4().hex
        outbound='Outgoing replica '+uuid.uuid4().hex
        with self.bind(ar,a):
            self.login();cid=a.create_chat(title);a.add_message(cid,'user','original context');sync.run()
        with self.bind(br,b):
            self.login();sync.run();bid=next(cid for cid,t,_ in b.list_chats() if t==title)
        with self.bind(ar,a):
            a.add_message(cid,'ai','remote addition');sync.run()
        with self.bind(br,b):
            local=b.create_chat(outbound);b.add_message(local,'user','completed during Live')
            result=sync.run(upload_only=True)
            self.assertEqual(result['received'],0)
            self.assertEqual([m.content for m in b.get_messages(bid)],['original context'])
            self.assertTrue(sync.read_ledger(sync.owner())['deferred'])
        with self.bind(cr,c):
            self.login();sync.run()
            imported=next(cid for cid,t,_ in c.list_chats() if t==outbound)
            self.assertEqual(c.get_messages(imported)[0].content,'completed during Live')
        with self.bind(br,b):
            sync.run()
            self.assertEqual([m.content for m in b.get_messages(bid)],['original context','remote addition'])
        for db in (a,b,c):db.close()

    def test_two_profiles_files_projects_edits_deletes_and_retry_budget(self):
        ar,a=self.profile('a');br,b=self.profile('b')
        material=ar/'attachment.txt';material.write_bytes(b'private attachment\n'*25000)
        chat=a.create_chat('Личный тестовый чат')
        a.add_message(chat,'user','Private content must remain encrypted',None,None,[('attachment.txt',str(material))])
        canvas_id=uuid.uuid4().hex
        a.set_setting('canvases_v1',json.dumps([{'id':canvas_id,'chat_id':chat,'name':'Canvas QA','mode':'code','content':'print(42)','strokes':[{'points':[[1,2],[3,4]],'color':'#ffffff'}]}]))
        wid=uuid.uuid4().hex
        a.set_setting('workspaces_v1',json.dumps({'items':[{'id':wid,'name':'QA project','icon':'code','instructions':'Secret project instructions','materials':[{'name':'attachment.txt','path':str(material)}]}],'chats':{str(chat):wid},'selected':'all'}))
        with self.bind(ar,a):
            self.login();result=sync.run();self.assertEqual(result['sent'],3)
            self.assertEqual(sync.run()['sent'],0)
            storage=cloud.request('/storage');self.assertEqual(storage['quota_bytes'],128*1024*1024)
            self.assertLess(storage['file_bytes'],material.stat().st_size//10)
            change=cloud.request('/sync/pull')['changes']
            raw=json.dumps(change);self.assertNotIn('Private content',raw);self.assertNotIn('Secret project',raw);self.assertNotIn(str(material),raw)
        with self.bind(br,b):
            self.login();self.assertEqual(sync.run()['received'],3)
            rows=b.list_chats();self.assertEqual(len(rows),1)
            imported=rows[0][0];messages=b.get_messages(imported)
            self.assertEqual(messages[0].content,'Private content must remain encrypted')
            copied=Path(messages[0].attachments[0][1]);self.assertTrue(copied.is_file());self.assertEqual(copied.read_bytes(),material.read_bytes())
            workspace=json.loads(b.get_setting('workspaces_v1'));self.assertEqual(workspace['chats'][str(imported)],wid)
            docs=json.loads(b.get_setting('canvases_v1'));self.assertEqual(docs[0]['chat_id'],imported);self.assertEqual(docs[0]['content'],'print(42)');self.assertEqual(docs[0]['strokes'][0]['points'],[[1,2],[3,4]])
            self.assertEqual(sync.run()['sent'],0)
            b.update_message(messages[0].id,'Edited on second profile')
            sync.run()
        with self.bind(ar,a):
            sync.run();self.assertEqual(a.get_messages(chat)[0].content,'Edited on second profile')
            a.delete_chat(chat);sync.run()
        with self.bind(br,b):
            # Reproduce a conflict persisted by the previous client version.
            apply=sync_entities.Entities._apply
            def old_apply(bridge,key,record,change,payload,current):
                hashes={k:r['hash'] for k,r in bridge.ledger['records'].items() if r['scope']=='workspaces'}
                result=apply(bridge,key,record,change,payload,current)
                if record['scope']=='chats' and payload is None:
                    for k,digest in hashes.items():bridge.ledger['records'][k]['hash']=digest
                return result
            with patch.object(sync_entities.Entities,'_apply',new=old_apply), \
                    patch.object(sync_entities.Entities,'recover_deleted_chat_conflicts'):
                self.assertEqual(sync.run()['conflicts'],1)
            result=sync.run();self.assertEqual(b.list_chats(),[])
            self.assertEqual(result['conflicts'],0,'Remote chat deletion must not conflict with its project')
            new=b.create_chat('Traffic limit test');b.add_message(new,'user','small text')
            # A pending upload remains durable when a budget forbids transport.
            sync.save_options({'traffic_limit':True,'daily_limit_bytes':1024})
            with self.assertRaisesRegex(RuntimeError,'лимит отправки'):sync.run()
            self.assertFalse(sync.status()['running'])
            sync.save_options({'traffic_limit':False});sync.run()
            queued=b.create_chat('Paused category');b.add_message(queued,'user','This selected-out item must wait')
            with patch.object(sync,'_flush',side_effect=RuntimeError('simulated interruption')):
                with self.assertRaisesRegex(RuntimeError,'interruption'):sync.run()
            self.assertTrue(sync.read_ledger(sync.owner()).get('pending'))
            sync.save_options({'chats':False});sync.run()
            self.assertTrue(sync.read_ledger(sync.owner()).get('parked'))
            sync.save_options({'chats':True});sync.run()
            self.assertFalse(sync.read_ledger(sync.owner()).get('parked'))
        with self.bind(ar,a):
            sync.run();self.assertIn('Traffic limit test',[row[1] for row in a.list_chats()]);self.assertIn('Paused category',[row[1] for row in a.list_chats()])

    def new_account(self):
        self.email='qa_'+uuid.uuid4().hex+'@example.invalid'
        pending=cloud._request(self.endpoint,'/auth/register',method='POST',body={'username':'QA','email':self.email,'password':self.password})
        code=(self.root/'mail'/hashlib.sha256(self.email.encode()).hexdigest()).read_text()
        cloud._request(self.endpoint,'/auth/verify-email',method='POST',body={'registration_id':pending['registration_id'],'code':code})

    def test_library_names_notes_and_later_material_enable_converge_after_reopen(self):
        self.new_account()
        ar,a=self.profile('library_desktop');br,b=self.profile('library_phone')
        with self.bind(ar,a):
            self.login()
            workspace=workspaces.create_workspace('Библиотека с ПК')
            wid=workspace['id']
            source=ar/'project'/'src';source.mkdir(parents=True)
            (source/'main.py').write_text('print("Desktop file")')
            materials,errors=library.import_folder(source.parent)
            self.assertEqual(errors,[])
            note=library.add_note('План','Текст заметки с ПК')
            library.append_materials(wid,[*materials,note])
            cid=a.create_chat('Связанный чат');a.add_message(cid,'user','Вопрос с ПК',attachments=[('src/main.py',materials[0]['path'])])
            workspaces.assign_chat(cid,wid)
            sync.save_options({'materials':False});sync.run()
        with self.bind(br,b):
            self.login();sync.run()
            self.assertEqual({entry['name'] for entry in library.entries(wid)},{'src/main.py','План.md'})
            imported=b.list_chats()[0][0]
            self.assertEqual(workspaces.chat_workspace(imported)['id'],wid)
            self.assertFalse(any(entry['available'] for entry in library.entries(wid)))
        with self.bind(ar,a):
            sync.save_options({'materials':True});sync.run()
        with self.bind(br,b):
            sync.run()
            entries=library.entries(wid)
            self.assertTrue(all(entry['available'] for entry in entries))
            plan=next(entry for entry in entries if entry['name']=='План.md')
            self.assertEqual(plan['type'],'Заметка')
            self.assertIn('Текст заметки с ПК',library.read_entry(plan)[0])
            self.assertEqual(b.get_messages(imported)[0].attachments[0][0],'src/main.py')
            library.update_note(wid,plan['id'],'План','Обновлено на телефоне')
            b.add_message(imported,'user','Ответ с телефона');sync.run()
        with self.bind(ar,a):
            sync.run()
            self.assertEqual(a.get_messages(cid)[-1].content,'Ответ с телефона')
            plan=next(entry for entry in library.entries(wid) if entry['type']=='Заметка')
            self.assertIn('Обновлено на телефоне',library.read_entry(plan)[0])
        # A fresh local connection keeps ledger bindings and imported copies.
        del b
        b=advanced_xopilot.PyDatabase(str(br/'xopilot.db'))
        with self.bind(br,b):
            result=sync.run()
            self.assertEqual(result['sent'],0);self.assertEqual(result['conflicts'],0)
            self.assertEqual(len(b.list_chats()),1)
            self.assertTrue(all(entry['available'] for entry in library.entries(wid)))

    def test_deferred_categories_and_conflicts_keep_both(self):
        self.new_account()
        ar,a=self.profile('conflict_a');br,b=self.profile('conflict_b')
        cid=a.create_chat('Conflict example');a.add_message(cid,'user','Original content')
        wid=uuid.uuid4().hex
        a.set_setting('workspaces_v1',json.dumps({'items':[{'id':wid,'name':'Deferred project','icon':'book','instructions':'','materials':[]}],'chats':{str(cid):wid},'selected':'all'}))
        with self.bind(ar,a):self.login();sync.run()
        with self.bind(br,b):
            self.login();sync.save_options({'workspaces':False});result=sync.run()
            self.assertEqual(result['received'],1);self.assertIsNone(b.get_setting('workspaces_v1'))
            sync.save_options({'workspaces':True});self.assertEqual(sync.run()['received'],1)
            imported=b.list_chats()[0][0];b.update_message(b.get_messages(imported)[0].id,'Local B branch')
        with self.bind(ar,a):a.update_message(a.get_messages(cid)[0].id,'Local A branch');sync.run()
        with self.bind(br,b):
            result=sync.run();self.assertEqual(result['conflicts'],1)
            self.assertEqual(b.get_messages(imported)[0].content,'Local B branch')
            key=next(iter(sync.conflict_items()));sync.resolve_keep_both(key)
            contents=[m.content for row in b.list_chats() for m in b.get_messages(row[0])]
            self.assertIn('Local A branch',contents);self.assertIn('Local B branch',contents)
            sync.run()
        with self.bind(ar,a):
            sync.run();contents=[m.content for row in a.list_chats() for m in a.get_messages(row[0])]
            self.assertIn('Local A branch',contents);self.assertIn('Local B branch',contents)

    def test_new_device_first_pull_after_linked_chat_was_already_deleted(self):
        self.new_account()
        ar,a=self.profile('deleted_first_a');br,b=self.profile('deleted_first_b')
        cid=a.create_chat('Already deleted before phone sign-in')
        a.add_message(cid,'user','Synthetic tombstone regression')
        wid=uuid.uuid4().hex
        a.set_setting('workspaces_v1',json.dumps({'items':[{'id':wid,'name':'Surviving project',
            'icon':'code','instructions':'','materials':[]}],'chats':{str(cid):wid},'selected':'all'}))
        with self.bind(ar,a):
            self.login();sync.run();a.delete_chat(cid);sync.run()
        with self.bind(br,b):
            self.login();result=sync.run()
            self.assertEqual(result['conflicts'],0)
            self.assertEqual(b.list_chats(),[])
            self.assertIn(wid,[item['id'] for item in workspaces.list_workspaces()])
            self.assertEqual(sync.run()['sent'],0)

    def test_bulk_delete_offline_survives_new_cloud_versions_and_restart(self):
        from App.services import chat_store
        self.new_account()
        ar,a=self.profile('bulk-delete-a');br,b=self.profile('bulk-delete-b')
        for index in range(3):
            cid=a.create_chat('Bulk deletion '+str(index));a.add_message(cid,'user','original')
        with self.bind(ar,a):self.login();sync.run()
        with self.bind(br,b):self.login();sync.run();self.assertEqual(len(b.list_chats()),3)
        with self.bind(ar,a),patch.object(chat_store,'get_db',return_value=a):
            self.assertEqual(chat_store.clear_all_chats(),3)
        with self.bind(br,b):
            for cid,_,_ in b.list_chats():b.add_message(cid,'ai','Newer remote version while phone offline')
            sync.run()
        a.close();a=advanced_xopilot.PyDatabase(str(ar/'xopilot.db'))
        try:
            with self.bind(ar,a):
                result=sync.run();self.assertEqual(result['conflicts'],0);self.assertEqual(a.list_chats(),[])
            with self.bind(br,b):
                sync.run();self.assertEqual(b.list_chats(),[])
                self.assertEqual(sync.run()['sent'],0)
            with self.bind(ar,a):sync.run();self.assertEqual(a.list_chats(),[])
        finally:a.close();b.close()

    def test_local_deletion_recovers_persisted_update_conflict_without_resurrection(self):
        self.new_account()
        ar,a=self.profile('deleted-conflict-a');br,b=self.profile('deleted-conflict-b')
        cid=a.create_chat('Deleted while conflict persisted');a.add_message(cid,'user','original')
        with self.bind(ar,a):self.login();sync.run()
        with self.bind(br,b):
            self.login();sync.run();bid=b.list_chats()[0][0]
            b.add_message(bid,'ai','cloud update');sync.run()
        with self.bind(ar,a):
            a.delete_chat(cid)
            change=cloud.request('/sync/pull')['changes'][-1]
            key=change['kind']+':'+change['id'];ledger=sync.read_ledger(sync.owner())
            ledger['records'][key]['blocked']=True;ledger['conflicts']={key:change}
            ledger['cursor']=change['sequence']
            a.set_setting(sync.ledger_key(sync.owner()),json.dumps(ledger))
            result=sync.run();self.assertEqual(result['conflicts'],0);self.assertEqual(a.list_chats(),[])
        with self.bind(br,b):sync.run();self.assertEqual(b.list_chats(),[])
        a.close();b.close()

    def test_protected_vault_transfers_only_after_close_temporary_never_transfers(self):
        from App.services.private_chats import PrivateChatSession
        self.new_account()
        ar,a=self.profile('private_a');br,b=self.profile('private_b')
        session=PrivateChatSession(root=ar/'private-chats')
        password='Synthetic private password!'
        cid=session.create(password);session.add_message(cid,'user','Protected private content')
        temporary=session.create(password,temporary=True);session.add_message(temporary,'user','Temporary never upload')
        with self.bind(ar,a):
            self.login();sync.save_options({'chats':False,'workspaces':False,'canvases':False,'protected':True})
            self.assertEqual(sync.run()['sent'],0)
            session.close(cid);self.assertEqual(sync.run()['sent'],1)
            raw=json.dumps(cloud.request('/sync/pull'));self.assertNotIn('Protected private content',raw);self.assertNotIn('Temporary never upload',raw)
        with self.bind(br,b):
            self.login();sync.save_options({'chats':False,'workspaces':False,'canvases':False,'protected':True})
            self.assertEqual(sync.run()['received'],1)
            received=PrivateChatSession(root=br/'private-chats')
            self.assertEqual(len(received.items()),1)
            received.unlock(cid,password);self.assertEqual(received.messages(cid)[0].content,'Protected private content');received.close_all()
        session.close_all()

    def test_unused_purged_copy_is_not_redownloaded_but_live_attachment_is(self):
        from App.services import storage
        self.new_account()
        ar,a=self.profile('cache_owner');br,b=self.profile('cache_receiver')
        file=ar/'qa-cache.txt';file.write_text('Owned cache regression material')
        cid=a.create_chat('Cache regression');a.add_message(cid,'user','with material',None,None,[('qa-cache.txt',str(file))])
        with self.bind(ar,a):self.login();sync.run()
        with self.bind(br,b),patch.object(storage,'app_data_dir',return_value=br),patch.object(storage,'get_db',return_value=b):
            self.login();sync.run()
            imported=b.list_chats()[0][0];local=b.get_messages(imported)[0].attachments[0][1]
            Path(local).unlink()
            sync.run();self.assertEqual(Path(local).read_text(),file.read_text())
            b.delete_chat(imported);sync.run()
            receipt=storage.trash_material(local);storage.purge_material(receipt)
            self.assertFalse(Path(local).exists())
            sync.run();sync.run()
            self.assertFalse(Path(local).exists())
            self.assertFalse(storage.local_inventory()['trash'])

    def test_cloud_material_exclusion_reinclude_and_private_conflict_recovery(self):
        from App.services import storage
        from App.services.private_chats import PrivateChatSession
        self.new_account()
        ar,a=self.profile('storage_a');br,b=self.profile('storage_b')
        file=ar/'test.txt';file.write_text('material payload'*1000)
        cid=a.create_chat('Storage example');a.add_message(cid,'user','with file',None,None,[('test.txt',str(file))])
        def bind_storage(root):return patch.object(storage,'app_data_dir',return_value=root)
        with self.bind(ar,a),bind_storage(ar),patch.object(storage,'get_db',return_value=a):
            self.login();sync.run();before=storage.cloud_inventory()['file_bytes'];self.assertGreater(before,0)
            storage.remove_cloud_material(str(file));self.assertEqual(storage.cloud_inventory()['file_bytes'],0)
            sync.run();self.assertTrue(file.exists())
            storage.include_cloud_material(str(file));sync.run();self.assertGreater(storage.cloud_inventory()['file_bytes'],0)
        with self.bind(br,b):
            self.login();sync.run();messages=b.get_messages(b.list_chats()[0][0]);self.assertEqual(Path(messages[0].attachments[0][1]).read_text(),file.read_text())
            with bind_storage(br),patch.object(storage,'get_db',return_value=b):
                local=messages[0].attachments[0][1];storage.delete_local_material(local)
                sync.run();self.assertFalse(Path(local).exists());self.assertGreater(storage.cloud_inventory()['file_bytes'],0)
                storage.restore_local_material(local);self.assertEqual(Path(local).read_text(),file.read_text())
                # Rewriting identical content must not resurrect a deleted blob identity.
                Path(local).write_text(file.read_text());sync.run()

        password='Synthetic private conflict password!'
        one=PrivateChatSession(root=ar/'private-chats');pid=one.create(password);one.add_message(pid,'user','initial');one.close_all()
        with self.bind(ar,a):sync.save_options({'protected':True});sync.run()
        with self.bind(br,b):sync.save_options({'protected':True});sync.run()
        two=PrivateChatSession(root=br/'private-chats');two.unlock(pid,password);two.add_message(pid,'user','B branch');two.close_all()
        one.unlock(pid,password);one.add_message(pid,'user','A branch');one.close_all()
        with self.bind(ar,a):sync.run()
        with self.bind(br,b),bind_storage(br),patch.object(storage,'get_db',return_value=b):
            self.assertEqual(sync.run()['conflicts'],1)
            key=next(iter(sync.conflict_items()));sync.resolve_private(key,'cloud')
            two.unlock(pid,password);self.assertEqual(two.messages(pid)[-1].content,'A branch');two.close_all()
            backups=storage.private_recoveries();self.assertTrue(backups)
            storage.restore_private_recovery(backups[0]['path'])
            two.unlock(pid,password);self.assertEqual(two.messages(pid)[-1].content,'B branch');two.close_all()

    def test_profile_avatar_name_are_encrypted_and_conflicts_preserve_versions(self):
        import io,base64
        from PIL import Image
        self.new_account()
        ar,a=self.profile('profile_a');br,b=self.profile('profile_b')
        image=io.BytesIO();Image.new('RGB',(320,480),'#00c9ac').save(image,'PNG')
        with self.bind(ar,a):
            self.login();profile.import_google(self.owner,name='Денис',avatar=profile.normalize_avatar(image.getvalue()),
                picture_url='https://lh3.googleusercontent.com/a/test-only')
            original=profile.read();self.assertEqual(sync.run()['sent'],1)
            raw=json.dumps(cloud.request('/sync/pull'));self.assertNotIn('Денис',raw);self.assertNotIn(original['avatar'],raw)
        with self.bind(br,b):
            self.login();self.assertEqual(sync.run()['received'],1);self.assertEqual(profile.read(),original)
            marker=json.loads(b.get_setting(profile.GOOGLE_SOURCE))
            self.assertEqual(marker,{'manual_name':True,'manual_avatar':True})
            profile.import_google('another-owner',name='Different Google name')
            self.assertEqual(profile.read(),original)
            profile.update(name='Денис B')
        with self.bind(ar,a):profile.update(name='Денис A');sync.run()
        with self.bind(br,b):
            self.assertEqual(sync.run()['conflicts'],1)
            key=next(iter(sync.conflict_items()));sync.resolve_profile(key,'cloud')
            self.assertEqual(profile.read()['name'],'Денис A')
            backups=json.loads(b.get_setting('profile_recovery_v1'));self.assertEqual(backups[-1]['profile']['name'],'Денис B')
            self.assertEqual(sync.run()['sent'],0)
            profile.restore_recovery(len(backups)-1)
            self.assertEqual(profile.read()['name'],'Денис B')
            self.assertEqual(profile.recoveries()[-1][1]['profile']['name'],'Денис A')
            profile.update(name='После перезапуска');sync.run()
        with self.bind(ar,a):sync.run();self.assertEqual(profile.read()['name'],'После перезапуска')
