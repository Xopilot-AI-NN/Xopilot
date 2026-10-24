"""
Файл: /tests/test_project_editor.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Проверяю редактор, сравнение версий, поиск и отказ от перезаписи внешних изменений.
          Исполнитель: Codex. Только временная SQLCipher и отдельные исходники.
"""
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,AsyncMock
from App.services import db,project_tools,workspaces,agent
from App.app.workspace import project_editor as ui
from App.app.theme.motion import switcher,refresh_preferences


class Page:
    height=850;width=1000;media=None
    def __init__(self):self.dialogs=[]
    def update(self):pass
    def show_dialog(self,value):value.open=True;self.dialogs.append(value)
    def pop_dialog(self):self.dialogs.pop().open=False


@unittest.skipIf(db.advanced_xopilot is None,'Native DB required')
class ProjectEditorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);self.project=root/'project';self.project.mkdir()
        self.native=db.advanced_xopilot.PyDatabase(str(root/'qa.db'),key='dc'*32);self.addCleanup(self.native.close)
        p=patch.object(db,'_db',self.native);p.start();self.addCleanup(p.stop)
        self.wid=workspaces.create_workspace('QA')['id'];project_tools.configure(self.wid,str(self.project))
        self.file=self.project/'main.py';self.file.write_text('port = 7791\n')
        self.page=Page()

    async def editor(self,name='main.py'):
        saved=AsyncMock();await ui.open_editor(self.page,self.wid,name,on_saved=saved)
        dialog=self.page.dialogs[-1];filename,tabs,host,metrics,status=dialog.content.controls
        code=host.controls[0].content.controls[1]
        return dialog,filename,tabs,host,code,status,saved

    async def test_compare_and_save_keeps_editor_and_updates_revision(self):
        dialog,filename,tabs,host,code,status,saved=await self.editor()
        code.value='port = 8892\n';code.on_change(SimpleNamespace(control=code))
        tabs.selected=['diff'];await tabs.on_change(SimpleNamespace(control=tabs))
        diff=host.controls[1].content.controls[0].value
        self.assertIn('-port = 7791',diff);self.assertIn('+port = 8892',diff)
        self.assertEqual(self.file.read_text(),'port = 7791\n')
        await dialog.actions[-1].on_click(None)
        self.assertIs(host.controls[0].content.controls[1],code)
        self.assertEqual(self.file.read_text(),'port = 8892\n');saved.assert_awaited_once()
        self.assertIn('сохранён',status.content.value)
        code.value='port = 9911\n';await dialog.actions[-1].on_click(None)
        self.assertEqual(self.file.read_text(),'port = 9911\n')
        dialog.actions[0].on_click(None);self.assertEqual(len(self.page.dialogs),0)

    async def test_external_change_is_not_overwritten_and_draft_can_be_kept(self):
        dialog,_,_,_,code,status,saved=await self.editor()
        code.value='my draft\n';self.file.write_text('external edit\n')
        await dialog.actions[-1].on_click(None)
        self.assertEqual(self.file.read_text(),'external edit\n');self.assertEqual(code.value,'my draft\n')
        self.assertIn('изменился',status.content.value);saved.assert_not_awaited()
        dialog.actions[0].on_click(None);confirm=self.page.dialogs[-1]
        self.assertIn('без сохранения',confirm.title.value)
        confirm.actions[0].on_click(None);self.assertIs(self.page.dialogs[-1],dialog)
        dialog.actions[0].on_click(None);self.page.dialogs[-1].actions[1].on_click(None)
        self.assertEqual(self.page.dialogs,[]);self.assertEqual(self.file.read_text(),'external edit\n')

    async def test_new_file_cannot_replace_an_existing_file_and_folder_switch_is_rejected(self):
        dialog,filename,_,_,code,status,_=await self.editor(None)
        filename.value='main.py';code.value='bad'
        await dialog.actions[-1].on_click(None)
        self.assertEqual(self.file.read_text(),'port = 7791\n');self.assertIn('изменился',status.content.value)
        filename.value='new.py';other=self.project.parent/'other';other.mkdir();project_tools.configure(self.wid,str(other))
        await dialog.actions[-1].on_click(None)
        self.assertFalse((other/'new.py').exists());self.assertIn('Папка проекта изменилась',status.content.value)

    async def test_search_selects_utf16_offsets_and_wraps_without_changing_text(self):
        _,_,_,host,code,status,_=await self.editor()
        code.value='🙂\nport=1\nPORT=2';query=host.controls[0].content.controls[0].controls[0];query.value='port'
        with patch.object(code,'focus',new=AsyncMock()):
            await query.on_submit(None)
            self.assertEqual((code.selection.base_offset,code.selection.extent_offset),(3,7))
            await query.on_submit(None);self.assertIn('строка 3',status.content.value)
            await query.on_submit(None);self.assertIn('строка 2',status.content.value)
        self.assertEqual(code.value,'🙂\nport=1\nPORT=2')

    def test_agent_rejects_changes_since_full_read(self):
        cid=self.native.create_chat('QA');workspaces.assign_chat(cid,self.wid)
        tools=agent.LocalTools(cid,threading.Event(),approve=lambda _:True)
        tools.call('read_project_file',{'path':'main.py'})
        self.file.write_text('external edit\n')
        with self.assertRaisesRegex(ValueError,'изменился'):tools.call('write_project_file',{'path':'main.py','content':'bad'})
        self.assertEqual(self.file.read_text(),'external edit\n')

    def test_diff_is_bounded_and_motion_respects_system_setting(self):
        text=ui.preview_diff('',('x'*100+'\n')*1000,'new.txt')
        self.assertIn('сокращён',text);self.assertLess(len(text),60500)
        self.page.__dict__['_xopilot_reduce_motion']=True
        animation=switcher(self.page,None)
        self.assertEqual(animation.duration,0);self.assertEqual(animation.reverse_duration,0)

    async def test_actual_accessibility_service_flags_update_registered_transitions(self):
        host=switcher(self.page,None)
        flags=SimpleNamespace(disable_animations=False,reduce_motion=True)
        service=SimpleNamespace(get_accessibility_features=AsyncMock(return_value=flags))
        with patch('App.app.theme.motion.ft.SemanticsService',return_value=service):
            self.assertTrue(await refresh_preferences(self.page))
        self.assertEqual(host.duration,0)
        self.assertEqual(switcher(self.page,None).duration,0)
        self.assertEqual(self.page.theme_animation_style.duration,0)

    async def test_repeated_tab_switches_keep_the_original_editable_control(self):
        _,_,tabs,host,code,_,_=await self.editor()
        for index in range(3):
            code.value='port = '+str(index)+'\n';code.on_change(SimpleNamespace(control=code))
            tabs.selected=['diff'];await tabs.on_change(SimpleNamespace(control=tabs))
            self.assertEqual(host.controls[0].opacity,0)
            self.assertTrue(host.controls[0].ignore_interactions)
            self.assertIn('+port = '+str(index),host.controls[1].content.controls[0].value)
            tabs.selected=['edit'];await tabs.on_change(SimpleNamespace(control=tabs))
            self.assertIs(host.controls[0].content.controls[1],code)
            self.assertEqual(host.controls[0].opacity,1)
            self.assertFalse(code.read_only)
