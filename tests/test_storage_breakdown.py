"""
Файл: /tests/test_storage_breakdown.py
Разработчик: DenBroLiik
Версия: 2.0.9
Описание: Полный облачный объём, общие блоки и безопасный viewport хранилища.
"""
import asyncio
import json
import tempfile
import uuid
from pathlib import Path
from contextlib import nullcontext
import unittest
from unittest.mock import Mock,patch
import flet as ft
from App.services import storage,cloud_account,cloud_sync,cloud_traffic,platforms
from App.settings.account import storage as ui

class StorageBreakdownTests(unittest.TestCase):
    def test_history_recovers_only_file_descriptions_without_restoring_chats(self):
        db=Mock();db.get_setting.return_value='a2V5'
        ledger={'records':{},'cursor':99,'assets':{}}
        manifest=dict(name='old.txt',size=9,sha256='a'*64,chunks=[str(uuid.uuid4())])
        change=dict(id=str(uuid.uuid4()),kind='chat',deleted=False,data={'scope':'chats','version':1,'ciphertext':'opaque'})
        replies=[{'changes':[change,dict(change,deleted=True,data={}),dict(change,id='private',data={'scope':'protected'})],'cursor':101,'has_more':False}]
        opts={'enabled':True,'materials':True,'chats':True,'workspaces':True}
        with tempfile.TemporaryDirectory() as folder,patch.object(storage,'app_data_dir',return_value=Path(folder)),\
                patch.object(storage,'get_db',return_value=db),patch.object(cloud_sync,'owner',return_value='owner'),\
                patch.object(cloud_sync,'options',return_value=opts),patch.object(cloud_sync,'read_ledger',return_value=ledger),\
                patch.object(cloud_traffic,'metered',return_value=nullcontext()),patch('App.services.sync_files.Files') as factory:
            files=factory.return_value;files.request.side_effect=replies
            files.decode.return_value={'title':'PRIVATE TRANSCRIPT','messages':[{'content':'not stored','attachments':[manifest]}]}
            result=storage.recover_cloud_materials()
        files.decode.assert_called_once_with(change['id'],change['data'])
        files.download_file.assert_not_called()
        saved=json.loads(db.set_setting.call_args.args[1])
        self.assertEqual(saved['cursor'],99)
        self.assertEqual(saved['records'],{})
        self.assertEqual(saved['storage_catalog_cursor'],101)
        self.assertEqual(result['found'],1)
        self.assertNotIn('PRIVATE TRANSCRIPT',json.dumps(saved))
        self.assertEqual(next(iter(saved['assets'].values()))['manifest'],manifest)

    def test_all_cloud_bytes_are_explained_even_when_device_knows_few_files(self):
        blobs=[dict(id=key,bytes=size,sync_payload=payload) for key,size,payload in (
            ('shared',100,False),('part',50,False),('profile',1000,True),('unknown',35000000,False))]
        pages=[dict(files=blobs[:2],has_more=True,next='part'),dict(files=blobs[2:],has_more=False,next='unknown')]
        for page in pages:page.update(used_bytes=35002500,quota_bytes=128*1024*1024,file_bytes=35001150,metadata_bytes=1350)
        ledger={'assets':{path:{'manifest':{'name':name,'size':80,'chunks':chunks}} for path,name,chunks in (
            ('/a','one.txt',['shared']),('/b','alias.txt',['shared']),('/c','two.txt',['shared','part']))}}
        with patch.object(cloud_sync,'owner',return_value='owner'),patch.object(cloud_sync,'read_ledger',return_value=ledger),\
                patch.object(cloud_traffic,'metered',return_value=nullcontext()),patch.object(cloud_account,'request',side_effect=pages) as request:
            inventory=storage.cloud_inventory()
        self.assertEqual(request.call_args.args[0],'/storage?after=part')
        self.assertEqual(len(inventory['materials']),2)
        self.assertEqual(inventory['material_bytes'],150)
        self.assertEqual(inventory['sync_payload_bytes'],1000)
        self.assertEqual(inventory['unmapped_files'][0]['id'],'unknown')
        self.assertEqual(sum(inventory[key] for key in ('material_bytes','sync_payload_bytes','unmapped_bytes','metadata_bytes')),inventory['used_bytes'])
        self.assertEqual(inventory['materials'][0]['aliases'],['one.txt','alias.txt'])

class StorageDialogTests(unittest.IsolatedAsyncioTestCase):
    async def test_inventory_poll_does_not_erase_ongoing_operation_status(self):
        page=Mock(width=393,height=851);page.show_dialog.side_effect=lambda dialog:setattr(dialog,'open',True)
        inventory=dict(used_bytes=0,quota_bytes=134217728,material_bytes=0,sync_payload_bytes=0,
            unmapped_bytes=0,metadata_bytes=0,materials=[],unmapped_files=[],excluded_materials=[])
        ticks=0
        async def tick(_):
            nonlocal ticks
            ticks+=1
            dialog=page.show_dialog.call_args.args[0]
            if ticks==1:dialog.content.controls[-1].value='Читаю описания…'
            else:dialog.open=False
        with patch.object(ui.cloud_account,'state',return_value={'account_id':'qa'}),patch.object(ui.navigation,'save'),\
                patch.object(ui.storage,'cloud_inventory',return_value=inventory),patch.object(ui.asyncio,'sleep',side_effect=tick):
            ui.open_storage(page,'cloud');dialog=page.show_dialog.call_args.args[0];page._dialogs.controls=[dialog]
            await page.run_task.call_args.args[0]()
        self.assertEqual(dialog.content.controls[-1].value,'Читаю описания…')

    async def test_cloud_summary_renders_finite_viewport_and_visible_close_action(self):
        page=Mock(width=393,height=851);page.show_dialog.side_effect=lambda dialog:setattr(dialog,'open',True)
        inventory=dict(used_bytes=35000000,quota_bytes=134217728,material_bytes=3000,sync_payload_bytes=2000,
            unmapped_bytes=34994000,metadata_bytes=1000,materials=[],unmapped_files=[dict(id='a',bytes=34994000)],
            excluded_materials=[],object_counts={'chat':2})
        async def stop(_):page.show_dialog.call_args.args[0].open=False
        page._dialogs.controls=[]
        with patch.object(ui.cloud_account,'state',return_value={'account_id':'qa'}),patch.object(ui.navigation,'save'),\
                patch.object(ui.storage,'cloud_inventory',return_value=inventory),patch.object(ui.asyncio,'sleep',side_effect=stop):
            ui.open_storage(page,'cloud');dialog=page.show_dialog.call_args.args[0]
            page._dialogs.controls=[dialog]
            await page.run_task.call_args.args[0]()
            self.assertIsInstance(dialog.content.controls[1],ft.ListView)
            self.assertTrue(dialog.content.controls[1].expand)
            self.assertIsNone(dialog.content.controls[1].height)
            self.assertIsInstance(dialog.content.height,(int,float))
            self.assertEqual(dialog.actions[0].content,'Готово')
            for height in (420,851):
                page.height=height;platforms.fit_dialog(page,dialog)
                self.assertLess(dialog.content.height,page.height)
                self.assertTrue(dialog.content.controls[1].expand)
            self.assertTrue(any(isinstance(c,ft.Text) and c.value=='Из чего складывается объём' for c in dialog.content.controls[1].controls))

    async def test_filter_uses_loaded_inventory_and_periodic_refresh_remains_fresh(self):
        page=Mock(width=393,height=851);page.show_dialog.side_effect=lambda dialog:setattr(dialog,'open',True)
        inventory=dict(used_bytes=0,quota_bytes=134217728,material_bytes=0,sync_payload_bytes=0,
            unmapped_bytes=0,metadata_bytes=0,materials=[],unmapped_files=[],excluded_materials=[])
        async def tick(seconds):
            if seconds>1:raise asyncio.CancelledError()
        with patch.object(ui.cloud_account,'state',return_value={'account_id':'qa'}),patch.object(ui.navigation,'save'),\
                patch.object(ui.storage,'cloud_inventory',return_value=inventory) as fetch,patch.object(ui.asyncio,'sleep',side_effect=tick):
            ui.open_storage(page,'cloud');dialog=page.show_dialog.call_args.args[0];page._dialogs.controls=[dialog]
            watch=page.run_task.call_args.args[0]
            with self.assertRaises(asyncio.CancelledError):await watch()
            filters=dialog.content.controls[1].controls[0];search=filters.controls[0]
            search.value='report';await search.on_change(None)
            search.value='report.py';await search.on_change(None)
            self.assertEqual(fetch.call_count,1,'Typing must not re-fetch cloud inventory')
            inventory['used_bytes']=9000
            with self.assertRaises(asyncio.CancelledError):await watch()
            self.assertEqual(fetch.call_count,2,'Periodic refresh must still read new cloud state')
            summary=dialog.content.controls[1].controls[1]
            self.assertIn('8',summary.content.controls[1].value)
            dialog.open=False;await search.on_change(None)
            self.assertEqual(fetch.call_count,2)
