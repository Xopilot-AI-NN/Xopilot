"""
Файл: /tests/test_task_execution.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Реальные процессы, пауза генерации, обрыв сети и пакеты действий.
          Исполнитель проверок: Codex.
"""
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, Mock
from concurrent.futures import CancelledError
from App.services import agent, project_tools, workspaces, task_processes, web_tools
from App.services.task_control import TaskControl


class Settings:
    def __init__(self):self.data={}
    def get_setting(self,key):return self.data.get(key)
    def set_setting(self,key,value):self.data[key]=value
    def get_messages(self,cid):return []


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.db=Settings()
        for module in (workspaces,project_tools):
            p=patch.object(module,'get_db',return_value=self.db);p.start();self.addCleanup(p.stop)
        self.workspace=workspaces.create_workspace('Task tests')['id']
        project_tools.configure(self.workspace,self.folder.name)
        workspaces.assign_chat(1,self.workspace)
        self.addCleanup(task_processes.stop_all)
        self.cancelled=threading.Event()

    def test_auto_agent_can_execute_more_than_sixteen_actions(self):
        responses=iter([json.dumps({'tool':'list_project_files','arguments':{}})]*20+[json.dumps({'final':'done'})])
        result=agent.run_agent('Inspect project',chat_id=1,history=[],attachments=[],instructions='',level='auto',
            cancelled=self.cancelled,generate=lambda *a,**k:next(responses))
        self.assertEqual(result.count('Файлы проекта · выполнено'),20)

    def test_parallel_real_commands_and_background_server_are_tracked(self):
        project_tools.set_chat_approval_mode(1,'automatic')
        commands=[{'tool':'run_project_command','arguments':{'argv':[sys.executable,'-c',f'import time; time.sleep(1); print({i})']}} for i in range(3)]
        responses=iter([json.dumps({'actions':commands}),json.dumps({'tool':'start_project_process','arguments':{
            'argv':[sys.executable,'-u','-c','import time; print("server ready"); time.sleep(30)']}}),json.dumps({'final':'done'})])
        review=Mock(return_value=False);start=time.monotonic()
        agent.run_agent('Run project',chat_id=1,history=[],attachments=[],instructions='',level='auto',
            cancelled=self.cancelled,approve=review,generate=lambda *a,**k:next(responses))
        self.assertLess(time.monotonic()-start,2.5) # Sequential execution would exceed 3 seconds.
        review.assert_not_called()
        items=task_processes.snapshots('chat:1',self.workspace)
        running=[p for p in items if p['running']];self.assertEqual(len(running),1)
        with self.assertRaises(ValueError):task_processes.get(running[0]['id'],'chat:2',self.workspace)
        time.sleep(.1)
        self.assertIn('server ready',task_processes.get(running[0]['id'],'chat:1',self.workspace).snapshot()['output'])
        task_processes.stop_all('chat:1')
        self.assertFalse(task_processes.has_running())

    def test_repeated_invalid_protocol_stops_without_an_unbounded_api_loop(self):
        generate=Mock(return_value='not a JSON action')
        with self.assertRaisesRegex(RuntimeError,'неверный формат'):
            agent.run_agent('Run',chat_id=1,history=[],attachments=[],instructions='',level='auto',
                cancelled=self.cancelled,generate=generate)
        self.assertEqual(generate.call_count,3)

    def test_manual_mode_is_default_and_denial_never_starts_process(self):
        self.assertEqual(project_tools.approval_mode(self.workspace),'manual')
        generate=iter([json.dumps({'tool':'run_project_command','arguments':{'argv':[sys.executable,'-c','print(1)']}}),
                       json.dumps({'final':'denied'})])
        review=Mock(return_value=False)
        before=len(task_processes.snapshots())
        result=agent.run_agent('Run',chat_id=1,history=[],attachments=[],instructions='',level='auto',
            cancelled=self.cancelled,approve=review,generate=lambda *a,**k:next(generate))
        review.assert_called_once();self.assertIn('не подтвердил',result)
        self.assertEqual(len(task_processes.snapshots()),before)
        with self.assertRaises(ValueError):project_tools.set_approval_mode('all','automatic')


class WebTests(unittest.TestCase):
    def test_private_network_and_mixed_dns_are_rejected_before_connect(self):
        for url in ('file:///etc/passwd','https://user:pass@example.com','http://localhost:7799'):
            with self.subTest(url=url),self.assertRaises(ValueError):web_tools.public_address(url)
        with patch.object(web_tools.socket,'getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',80))]):
            with self.assertRaises(ValueError):web_tools.public_address('http://example.com')
        with patch.object(web_tools.socket,'getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',80)),(2,1,6,'',('169.254.169.254',80))]):
            with self.assertRaises(ValueError):web_tools.public_address('http://example.com')

    def test_readable_text_links_and_search_results(self):
        html='<title>Example</title><script>steal()</script><h1>Привет</h1><a href="/next">Next</a>'
        with patch.object(web_tools,'fetch',return_value=('https://example.com',html)):
            result=web_tools.read('https://example.com')
        self.assertIn('Привет',result['text']);self.assertNotIn('steal',result['text'])
        self.assertEqual(result['links'][0]['url'],'https://example.com/next')
        html='<a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com">Example site</a>'
        with patch.object(web_tools,'fetch',return_value=('https://html.duckduckgo.com/html',html)):
            self.assertEqual(web_tools.search('Example')['results'][0]['url'],'https://example.com')

    def test_redirect_to_private_address_is_revalidated(self):
        with patch.object(web_tools,'public_address',side_effect=[(web_tools.urlsplit('https://example.com'),443,'8.8.8.8'),ValueError('private')]),\
             patch.object(web_tools.http.client,'HTTPSConnection') as connection:
            response=connection.return_value.getresponse.return_value
            response.status=302;response.getheader.return_value='http://127.0.0.1'
            with self.assertRaisesRegex(ValueError,'private'):web_tools.fetch('https://example.com')
            self.assertEqual(connection.call_count,1)
