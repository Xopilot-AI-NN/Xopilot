"""
Файл: /tests/test_project_inspection.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Проверяю поиск по коду, диапазоны строк, Git diff и границы выбранной папки.
          Исполнитель: Codex. Только временные проекты и Git-репозитории.
"""
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from App.services import db,project_tools,project_inspection as inspect,workspaces,agent,agent_protocol


@unittest.skipIf(db.advanced_xopilot is None,'Native DB required')
class ProjectInspectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.project=self.root/'project';self.project.mkdir()
        self.native=db.advanced_xopilot.PyDatabase(str(self.root/'qa.db'),key='ee'*32);self.addCleanup(self.native.close)
        p=patch.object(db,'_db',self.native);p.start();self.addCleanup(p.stop)
        self.wid=workspaces.create_workspace('QA')['id'];project_tools.configure(self.wid,str(self.project))
        self.cid=self.native.create_chat('QA');workspaces.assign_chat(self.cid,self.wid)
        (self.project/'main.py').write_text('def serve():\n    port = 7791\n    return port\n',encoding='utf-8')

    def test_search_has_lines_pagination_and_skips_secrets_symlinks_and_build_output(self):
        (self.project/'other.py').write_text('port = 2\nport = 3\n',encoding='utf-8')
        for folder in ('build','node_modules','.ssh'):
            (self.project/folder).mkdir();(self.project/folder/'secret.py').write_text('port = SECRET')
        (self.project/'.env').write_text('port = SECRET');(self.project/'binary.py').write_bytes(b'port\0secret')
        outside=self.root/'outside.py';outside.write_text('port = SECRET')
        (self.project/'link.py').symlink_to(outside)
        first=inspect.search(self.wid,'PORT',pattern='*.py',limit=2)
        second=inspect.search(self.wid,'PORT',pattern='*.py',limit=2,offset=first['next_offset'])
        hits=first['matches']+second['matches']
        self.assertEqual([(r['path'],r['line']) for r in hits],[('main.py',2),('main.py',3),('other.py',1),('other.py',2)])
        self.assertTrue(first['has_more']);self.assertFalse(second['has_more'])
        self.assertTrue(all('SECRET' not in r['text'] for r in hits));self.assertEqual(first['skipped_files'],1)

    def test_line_ranges_are_typed_and_cannot_overwrite_a_file_until_full_read(self):
        value=project_tools.read_file(self.wid,'main.py',start_line=2,end_line=2)
        self.assertEqual(value['content'],'    port = 7791\n');self.assertEqual(value['next_line'],3)
        for start,end in [(0,1),(True,2),(3,2),(1,501)]:
            with self.assertRaises(ValueError):project_tools.read_file(self.wid,'main.py',start_line=start,end_line=end)
        tools=agent.LocalTools(self.cid,threading.Event(),approve=lambda _:True)
        tools.call('read_project_file',{'path':'./main.py','start_line':2,'end_line':2})
        with self.assertRaisesRegex(ValueError,'полностью'):tools.call('write_project_file',{'path':'main.py','content':'bad'})
        self.assertIn('def serve', (self.project/'main.py').read_text())
        tools.call('read_project_file',{'path':'main.py'})
        tools.call('write_project_file',{'path':'main.py','content':'full replacement\n'})
        self.assertEqual((self.project/'main.py').read_text(),'full replacement\n')
        schema=agent_protocol.native_tools({'read_project_file':agent.TOOLS['read_project_file']})[0]['function']['parameters']
        self.assertEqual(schema['properties']['start_line']['minimum'],1)

    @unittest.skipUnless(shutil.which('git'),'Git required')
    def test_git_status_working_staged_diff_and_filters_do_not_execute(self):
        def git(*args):return subprocess.run(['git',*args],cwd=self.project,check=True,capture_output=True)
        git('init');git('config','user.name','QA');git('config','user.email','qa@example.invalid')
        git('add','main.py');git('commit','-m','QA base')
        (self.project/'main.py').write_text('def serve():\n    port = 8892\n    return port\n')
        status=inspect.git(self.wid);self.assertIn('main.py',[r['path'] for r in status['files']])
        diff=inspect.git(self.wid,'diff',path='main.py')['diff'];self.assertIn('-    port = 7791',diff);self.assertIn('+    port = 8892',diff)
        git('add','main.py')
        self.assertIn('8892',inspect.git(self.wid,'staged_diff',path='main.py')['diff'])
        self.assertEqual(inspect.git(self.wid,'diff',path='main.py')['diff'],'')
        (self.project/'.env').write_text('SECRET');self.assertNotIn('.env',[r['path'] for r in inspect.git(self.wid)['files']])
        with self.assertRaises(ValueError):inspect.git(self.wid,'diff',path='../outside')
        with self.assertRaises(ValueError):inspect.git(self.wid,'diff',path='.env')
        # A clean filter would write a marker if a nominally read-only Git action executed it.
        marker=self.root/'filter-ran'
        script=self.root/'filter.py';script.write_text('import pathlib,sys\npathlib.Path('+repr(str(marker))+').write_text("bad")\nsys.stdout.write(sys.stdin.read())\n')
        import sys,shlex
        git('config','filter.qa.clean',shlex.join([sys.executable,str(script)]))
        (self.project/'.gitattributes').write_text('*.py filter=qa\n')
        (self.project/'main.py').write_text('port = 9911\n')
        inspect.git(self.wid);inspect.git(self.wid,'diff',path='main.py')
        self.assertFalse(marker.exists())
        child=self.project/'child';child.mkdir();project_tools.configure(self.wid,str(child))
        with self.assertRaisesRegex(ValueError,'корень'):inspect.git(self.wid)

    async def test_project_search_ui_opens_matching_file(self):
        from App.app.workspace.project_inspection import open_search
        class Page:
            height=800
            def update(self):pass
            def show_dialog(self,value):self.dialog=value
            def pop_dialog(self):self.dialog=None
        page=Page();opened=[]
        async def on_open(path):opened.append(path)
        open_search(page,self.wid,on_open)
        controls=page.dialog.content.controls;controls[0].value='7791';controls[1].value='*.py'
        await controls[2].on_click(None)
        await controls[-2].controls[0].on_click(None)
        self.assertEqual(opened,['main.py']);self.assertIsNone(page.dialog)

    async def test_search_pagination_resets_when_query_changes(self):
        from App.app.workspace.project_inspection import open_search
        class Page:
            height=800
            def update(self):pass
            def show_dialog(self,value):self.dialog=value
            def pop_dialog(self):self.dialog=None
        (self.project/'many.py').write_text('port = 1\n'*45+'unique = 1\n')
        page=Page()
        async def on_open(path):pass
        open_search(page,self.wid,on_open)
        controls=page.dialog.content.controls;controls[0].value='port'
        await controls[2].on_click(None)
        self.assertTrue(controls[-1].visible)
        controls[0].value='unique'
        await controls[-1].on_click(None)
        self.assertEqual(len(controls[-2].controls),1)
        self.assertEqual(controls[-2].controls[0].content.controls[0].value,'many.py:46')

    def test_tool_discovery_and_project_access(self):
        from App.services import tool_discovery
        access={'enabled':True,'root':str(self.project)}
        with patch('App.services.platforms.is_android',return_value=False):
            available=agent.available_tools(access,self.wid)
            self.assertIn('search_project',tool_discovery.discover('поиск функции по коду',available))
            self.assertIn('git_project',tool_discovery.discover('git diff',available))
            self.assertNotIn('git_project',agent.available_tools({},self.wid))
        with patch('App.services.platforms.is_android',return_value=True):
            self.assertNotIn('git_project',agent.available_tools(access,self.wid))
            self.assertNotIn('search_project',agent.available_tools(access,self.wid))

    @unittest.skipUnless(shutil.which('git'),'Git required')
    async def test_git_ui_displays_real_working_diff(self):
        from App.app.workspace.project_inspection import open_git
        def git(*args):return subprocess.run(['git',*args],cwd=self.project,check=True,capture_output=True)
        git('init');git('config','user.name','QA');git('config','user.email','qa@example.invalid')
        git('add','main.py');git('commit','-m','QA')
        (self.project/'main.py').write_text('port = 9911\n')
        class Page:
            height=800
            def update(self):pass
            def show_dialog(self,value):self.dialog=value
            def pop_dialog(self):pass
            def run_task(self,callback):self.callback=callback
        page=Page();open_git(page,self.wid);await page.callback()
        row=page.dialog.content.controls[-1].controls[0]
        self.assertIn('main.py',row.content.controls[0].value)
        await row.content.controls[1].controls[0].on_click(None)
        self.assertIn('+port = 9911',page.dialog.content.controls[0].value)

    async def test_project_panel_filters_filenames_and_disables_tools_after_disconnect(self):
        from App.app.workspace.project_browser import open_project
        class Page:
            height=800;width=1000;web=True
            def update(self):pass
            def show_dialog(self,value):self.dialog=value;value.open=True
            def pop_dialog(self):self.dialog.open=False
            def run_task(self,callback,*args):self.callback=callback;self.args=args
        page=Page();open_project(page,{'id':self.wid,'name':'QA'})
        await page.callback(*page.args)
        controls=page.dialog.content.controls;tools=controls[2];query=controls[3];rows=controls[4]
        self.assertTrue(all(not b.disabled for b in tools.controls))
        self.assertEqual(rows.controls[0].content.controls[1].value,'main.py')
        query.value='absent';query.on_change(None)
        self.assertEqual(rows.controls[0].content.controls[1].value,'Нет совпадений')
        query.suffix.on_click(None)
        self.assertEqual(query.value,'')
        self.assertEqual(rows.controls[0].content.controls[1].value,'main.py')
        disconnect=controls[0].content.controls[2].controls[-1]
        await disconnect.on_click(None)
        self.assertTrue(all(b.disabled for b in tools.controls))
        self.assertEqual(controls[0].content.controls[0].controls[1].controls[1].value,'Папка не подключена')
