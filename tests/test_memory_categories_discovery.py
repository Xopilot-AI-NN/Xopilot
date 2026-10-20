"""
Файл: /tests/test_memory_categories_discovery.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Категории, выборочная память, изоляция проектов и ленивые схемы инструментов.
          Исполнитель: Codex.
"""
import json
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from App.services import db,user_memory as memory,profile,workspaces,agent,tool_discovery


@unittest.skipIf(db.advanced_xopilot is None,'Native DB required')
class CategorizedMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.native=db.advanced_xopilot.PyDatabase(str(Path(self.temp.name)/'qa.db'),key='cb'*32)
        self.addCleanup(self.native.close)
        p=patch.object(db,'_db',self.native);p.start();self.addCleanup(p.stop)
        self.a=workspaces.create_workspace('Atlas')['id'];self.b=workspaces.create_workspace('Other')['id']
        self.cid=self.native.create_chat('QA');workspaces.assign_chat(self.cid,self.a)

    def test_only_relevant_memory_is_loaded_and_project_facts_do_not_leak(self):
        memory.save('Я предпочитаю Python',category='preferences')
        memory.save('Я люблю апельсины',category='preferences')
        memory.save('Проект Atlas: порт 7791',category='projects',workspace_id=self.a)
        memory.save('Другой проект: порт 8892',category='projects',workspace_id=self.b)
        text=memory.context('Python',workspace_id=self.a)
        self.assertIn('Python',text);self.assertNotIn('апельсины',text);self.assertNotIn('7791',text)
        text=memory.context('порт',workspace_id=self.a)
        self.assertIn('7791',text);self.assertNotIn('8892',text)
        self.assertNotIn('7791',memory.context('порт'))
        self.assertEqual(memory.context('Привет'), '')
        self.assertEqual(memory.context(), '')

    def test_capture_assigns_project_category_and_sync_keeps_scope(self):
        message='Запомни: проект Atlas использует порт 7791'
        memory.capture(message,lambda *_args,**_kw:'{}',workspace_id=self.a)
        item=memory.read()['items'][0]
        self.assertEqual(item['category'],'projects');self.assertEqual(item['workspace_id'],self.a)
        normalized=profile.validate(profile.read())
        self.assertEqual(normalized['memory']['items'][0]['workspace_id'],self.a)
        memory.save('Проект Atlas теперь использует порт 7792',item['id'])
        self.assertEqual(memory.read()['items'][0]['workspace_id'],self.a)

    def test_initial_tool_schema_is_only_catalog_then_selected_memory_tools(self):
        memory.save('Имя пользователя: Ника')
        calls=[]
        def generate(prompt,**options):
            names={t['function']['name'] for t in options['native_tools']};calls.append(names)
            if len(calls)==1:
                self.assertEqual(names,{'discover_tools'})
                return json.dumps({'tool':'discover_tools','arguments':{'query':'memory'}})
            if len(calls)==2:
                self.assertIn('search_memory',names);self.assertNotIn('create_canvas',names)
                return json.dumps({'tool':'search_memory','arguments':{'query':'имя'}})
            self.assertIn('Ника',prompt)
            return json.dumps({'final':'Ника'})
        reply=agent.run_agent('Найди в памяти моё имя',chat_id=self.cid,history=[],attachments=[],instructions='',level='auto',network=True,cancelled=threading.Event(),generate=generate)
        self.assertIn('Ника',reply);self.assertEqual(len(calls),3)

    def test_discovery_does_not_expose_unsupported_project_commands(self):
        allowed=agent.available_tools({'enabled':False,'root':None},self.a)
        chosen=tool_discovery.discover('project command',allowed)
        self.assertNotIn('run_project_command',chosen)
        self.assertNotIn('read_project_file',chosen)

    def test_repeated_catalog_without_progress_stops_and_is_not_reported_as_success(self):
        calls=[]
        def generate(*_args,**_options):
            calls.append(1)
            return json.dumps({'tool':'discover_tools','arguments':{'query':'nonexistent_function_xyz'}})
        with self.assertRaisesRegex(RuntimeError,'каталога'):
            agent.run_agent('Найди файл',chat_id=self.cid,history=[],attachments=[],instructions='',level='auto',network=True,cancelled=threading.Event(),generate=generate)
        self.assertEqual(len(calls),3)

    def test_category_queries_return_only_requested_scope_and_disabled_memory_is_unavailable(self):
        memory.save('Я предпочитаю Python',category='preferences')
        memory.save('Проект Atlas использует Rust',category='projects',workspace_id=self.a)
        memory.save('Проект Other использует Java',category='projects',workspace_id=self.b)
        self.assertEqual([r['text'] for r in memory.search(category='projects',workspace_id=self.a)],['Проект Atlas использует Rust'])
        self.assertEqual(memory.search(category='projects'),[])
        memory.configure(enabled=False)
        self.assertEqual(memory.context('Python'), '')
        self.assertNotIn('search_memory',agent.available_tools({'enabled':False},self.a))

    def test_exact_tool_name_does_not_load_similarly_named_tools(self):
        available=agent.available_tools({'enabled':False},self.a)
        self.assertEqual(list(tool_discovery.discover('search_memory',available)),['search_memory'])
        self.assertEqual(set(tool_discovery.discover('memory',available)),{'search_memory','save_memory'})
