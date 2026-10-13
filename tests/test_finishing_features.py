"""Real file/process checks and regression coverage for the user's last issues."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch,AsyncMock
import flet as ft
from App.services import project_tools,workspaces,agent,canvases,material_store,storage,cloud_account
from App.app import canvas_editor,material
from App.services import user_memory as memory

class Settings:
    def __init__(self):self.data={}
    def get_setting(self,k):return self.data.get(k)
    def set_setting(self,k,v):self.data[k]=v
    def list_chats(self):return []

class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.db=Settings()
        for module in (workspaces,project_tools,canvases,storage):
            p=patch.object(module,'get_db',return_value=self.db);p.start();self.addCleanup(p.stop)
        self.workspace=workspaces.create_workspace('Own QA project')['id']
        project_tools.configure(self.workspace,str(self.root))
        self.cancelled=threading.Event()

    def test_reviewed_write_read_compile_and_process_output_are_real(self):
        approved=[]
        source='print(19+23)\n'
        result=project_tools.write_file(self.workspace,'src/main.py',source,self.cancelled,lambda r:approved.append(r) or True)
        self.assertTrue(result['saved']);self.assertEqual((self.root/'src/main.py').read_text(),source)
        self.assertEqual(project_tools.read_file(self.workspace,'src/main.py')['content'],source)
        with patch.object(project_tools,'is_android',return_value=False):
            result=project_tools.run_command(self.workspace,[sys.executable,'src/main.py'],self.cancelled,lambda r:approved.append(r) or True)
        self.assertEqual(result['exit_code'],0);self.assertEqual(result['output'].strip(),'42')
        self.assertEqual(approved[-1]['cwd'],str(self.root))

    def test_no_write_or_execution_without_approval_or_outside_folder(self):
        with self.assertRaisesRegex(ValueError,'не подтвердил'):
            project_tools.write_file(self.workspace,'denied.py','text',self.cancelled,lambda _:False)
        self.assertFalse((self.root/'denied.py').exists())
        for name in ('../outside','/etc/passwd','.env','.git/config'):
            with self.subTest(name=name),self.assertRaises(ValueError):project_tools.read_file(self.workspace,name)
        (self.root/'linked').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):project_tools.read_file(self.workspace,'linked')
        with patch.object(project_tools,'is_android',return_value=False),patch.object(project_tools.subprocess,'Popen') as process:
            with self.assertRaisesRegex(ValueError,'не подтвердил'):
                project_tools.run_command(self.workspace,[sys.executable,'-c','print(42)'],self.cancelled,lambda _:False)
            process.assert_not_called()

    def test_file_changed_while_reviewing_is_not_overwritten(self):
        (self.root/'a.py').write_text('before')
        def approve(_):(self.root/'a.py').write_text('external edit');return True
        with self.assertRaisesRegex(ValueError,'изменился'):
            project_tools.write_file(self.workspace,'a.py','after',self.cancelled,approve)
        self.assertEqual((self.root/'a.py').read_text(),'external edit')

    def test_agent_creates_and_updates_persisted_canvas_for_explicit_request(self):
        cid=4;workspaces.assign_chat(cid,self.workspace)
        generator=Mock(side_effect=[json.dumps({'final':'I made it (but did not)'}),
            json.dumps({'tool':'create_canvas','arguments':{'title':'main.py','kind':'code','content':'print(42)'}}),
            json.dumps({'final':'Файл создан'})])
        result=agent.run_agent('Создай файл main.py в Canvas',chat_id=cid,history=[],attachments=[],instructions='',
            level='auto',cancelled=self.cancelled,generate=generator)
        docs=canvases.list_documents(cid,self.workspace)
        self.assertEqual(len(docs),1);self.assertEqual(docs[0]['content'],'print(42)')
        self.assertIn('Создание Canvas',result)
        tools=agent.LocalTools(cid,self.cancelled)
        tools.call('update_canvas',{'id':docs[0]['id'],'content':'print(43)'})
        self.assertEqual(canvases.get_document(docs[0]['id'])['content'],'print(43)')
        self.assertEqual(canvases.export_document(docs[0])[0],'main.py')
        self.assertTrue(agent.needs_tools('Скомпилируй проект'));self.assertFalse(agent.needs_tools('Как создать файл?'))

    def test_drawing_surface_has_no_scroll_parent_and_saved_strokes_export(self):
        page=Mock(width=393,height=851,web=False)
        with patch.object(canvas_editor,'is_android',return_value=False):
            dialog=canvas_editor.build_canvas_dialog(page,4,document_store=canvases)
        dialog.content.controls[2].value='drawing';dialog.content.controls[2].on_select(None)
        drawing_area=dialog.content.controls[4]
        with patch.object(canvas_editor,'is_android',return_value=False):
            asyncio.run(drawing_area.controls[0].on_click(None))
        draw_dialog=page.show_dialog.call_args.args[0]
        self.assertIsNone(draw_dialog.content.scroll)
        detector=draw_dialog.content.controls[1].content
        with patch.object(canvas_editor.cv.Canvas,'update'):
            detector.on_pan_start(SimpleNamespace(local_position=SimpleNamespace(x=10,y=10)))
            detector.on_pan_update(SimpleNamespace(local_position=SimpleNamespace(x=70,y=80)))
        detector.on_pan_end(None)
        doc=canvases.list_documents(4)[0]
        doc['kind']='drawing'
        name,data=canvases.export_document(doc)
        from PIL import Image
        import io
        image=Image.open(io.BytesIO(data));self.assertTrue(name.endswith('.png'))
        self.assertLess(len(set(image.getdata())),100)
        self.assertGreater(len(set(image.getdata())),1)

    def test_delete_last_canvas_closes_editor_without_recreating_document(self):
        page=Mock(width=393,height=851,web=False)
        with patch.object(canvas_editor,'is_android',return_value=False):
            dialog=canvas_editor.build_canvas_dialog(page,4,document_store=canvases)
        self.assertEqual(len(canvases.list_documents(4)),1)
        dialog.content.controls[0].controls[2].on_click(None)
        confirmation=page.show_dialog.call_args.args[0]
        confirmation.actions[1].on_click(None)
        self.assertEqual(canvases.list_documents(4),[])
        self.assertEqual(page.pop_dialog.call_count,2)

    def test_deduplicated_materials_and_cleanup_never_remove_referenced_files(self):
        for module in (material_store,storage):
            p=patch.object(module,'app_data_dir',return_value=self.root);p.start();self.addCleanup(p.stop)
        with patch.object(storage,'models_dir',return_value=self.root/'models'):
            first=Path(material_store.store_material('a.txt',data=b'same'))
            second=Path(material_store.store_material('b.txt',data=b'same'))
            if sys.platform!='win32':self.assertEqual(first.stat().st_ino,second.stat().st_ino)
            workspaces.update_workspace(self.workspace,'Own QA project',materials=[{'name':'a.txt','path':str(first)}])
            inventory=storage.local_inventory();self.assertEqual(inventory['materials_bytes'],4)
            removed=storage.remove_unused_materials()
            self.assertEqual(removed['count'],1);self.assertTrue(first.is_file());self.assertFalse(second.exists())

class DeviceAndMemoryTests(unittest.TestCase):
    def test_android_uses_actual_model_not_localhost(self):
        db=Settings();db.set_setting('device_info_v1',json.dumps({'name':'POCO X5 5G','region':'BY'}))
        with patch.object(cloud_account,'get_db',return_value=db),patch('App.services.platforms.is_android',return_value=True):
            self.assertEqual(cloud_account._device(),'POCO X5 5G')

    def test_memory_does_not_call_model_for_name_questions_or_one_off_requests(self):
        generate=Mock()
        for text in ('как меня зовут','Как меня зовут?','Напиши мне код','Мне нужно сделать файл','Я нажал на кнопку'):
            self.assertEqual(memory.capture(text,generate),[])
        generate.assert_not_called()
        self.assertEqual(memory._fact('Меня зовут Денис'),('Имя пользователя: Денис','name'))
        self.assertIsNone(memory._fact('как меня зовут'))

class ChatPreviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_material_click_uses_shared_viewer(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'a.txt';path.write_text('actual content')
            with patch('App.app.material_viewer.open_material',new=AsyncMock()) as view:
                tile=material.build_file_tile(ft.FilePickerFile(id=1,name='a.txt',path=str(path),size=14))
                page=Mock();await tile.on_click(SimpleNamespace(page=page))
                view.assert_awaited_once_with(page,str(path),'a.txt')
