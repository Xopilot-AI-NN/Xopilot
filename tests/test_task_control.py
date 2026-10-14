"""
Файл: /tests/test_task_control.py
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


class ControllerTests(unittest.TestCase):
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

    def test_pause_interrupts_inference_and_resume_retries_only_inference(self):
        started=threading.Event();interrupted=threading.Event();calls=[];result=[]
        task=TaskControl()
        def generate(prompt,cancelled,**kwargs):
            calls.append(prompt)
            if len(calls)==1:
                started.set()
                while not cancelled.is_set():time.sleep(.01)
                interrupted.set();raise CancelledError()
            return 'continued'
        thread=threading.Thread(target=lambda:result.append(task.generate(generate,'prompt')))
        thread.start();self.assertTrue(started.wait(2))
        task.pause();self.assertTrue(interrupted.wait(2))
        time.sleep(.1);self.assertEqual(calls,['prompt']);self.assertTrue(thread.is_alive())
        task.resume();thread.join(2)
        self.assertEqual(result,['continued']);self.assertEqual(len(calls),2)

    def test_network_failure_pauses_model_but_keeps_local_process_and_resumes(self):
        process=project_tools.start_command(self.workspace,[sys.executable,'-u','-c','import time; print("alive"); time.sleep(30)'],
            self.cancelled,lambda _:True,'network-test')
        task=TaskControl();failed=threading.Event();online=threading.Event();result=[]
        calls=[]
        def generate(prompt,**kwargs):
            calls.append(prompt)
            if len(calls)==1:failed.set();raise ConnectionResetError('test network drop')
            return 'restored'
        thread=threading.Thread(target=lambda:result.append(task.generate(generate,'prompt',network=True,probe=online.is_set)))
        thread.start();self.assertTrue(failed.wait(2));time.sleep(.05)
        self.assertTrue(task.paused)
        self.assertTrue(task_processes.get(process['id'],'network-test',self.workspace).snapshot()['running'])
        self.assertEqual(len(calls),1)
        online.set();thread.join(4)
        self.assertEqual(result,['restored']);self.assertEqual(len(calls),2)
        self.assertTrue(task_processes.get(process['id'],'network-test',self.workspace).snapshot()['running'])

    def test_auth_error_is_not_retried_as_lost_network(self):
        generate=Mock(side_effect=RuntimeError('HTTP 401'))
        with self.assertRaisesRegex(RuntimeError,'401'):
            TaskControl().generate(generate,'prompt',network=True,probe=lambda:True)
        self.assertEqual(generate.call_count,1)

