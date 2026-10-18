"""Файл: /tests/test_local_models_integration.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Реальные задания инструментов Gemma в изолированной БД и папке.
          Запуск: XOPILOT_TEST_MODELS=имя.litertlm python -m unittest ...
          Модели не скачиваются автоматически; личные данные не используются.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from App.services import db, llm, workspaces, library, canvases, project_tools, context_budget
from App.services.agent import run_agent


@unittest.skipUnless(os.environ.get('XOPILOT_TEST_MODELS'), 'Opt-in real local model test')
class LocalModelIntegrationTests(unittest.TestCase):
    def test_compaction_keeps_middle_facts_and_latest_correction(self):
        import copy
        for filename in os.environ['XOPILOT_TEST_MODELS'].split(','):
            with self.subTest(model=filename), tempfile.TemporaryDirectory(prefix='xopilot-real-context-') as folder:
                native=db.advanced_xopilot.PyDatabase(str(Path(folder)/'qa.db'),key='42'*32)
                with patch.object(db,'_db',native), patch.dict(os.environ,XDG_DATA_HOME=folder):
                    native.set_setting('inference_backend','gpu')
                    history=[{'role':'user','content':'Меня зовут Иван. Проект Xopilot. Порт 7799.'}]
                    history += [{'role':'ai','content':'Обсуждаем расположение кнопок и библиотеку документов. ' * 30} for _ in range(8)]
                    history.insert(4,{'role':'user','content':
                        'Обсуждаем внешний вид. ' * 100 +
                        'Исправление: меня зовут Денис. Порт 8800 вместо 7799. Файл src/server.py. '
                        'Не удаляй файлы проекта. Команды запускай только после подтверждения. ' +
                        'Продолжаем обсуждение. ' * 100})
                    original=copy.deepcopy(history)
                    event=threading.Event();timer=threading.Timer(240,event.set);timer.start()
                    try:
                        llm.load_model(filename)
                        answer=llm.generate_reply('Назови актуальные имя пользователя, название проекта, порт и путь файла. '
                            'Можно ли удалять файлы и запускать команды без подтверждения? Ответь кратко.',history=history,cancelled=event)
                        print('CONTEXT',filename,answer,flush=True)
                        for value in ('Денис','Xopilot','8800','src/server.py'):
                            self.assertIn(value,answer)
                        self.assertNotIn('Иван',answer)
                        self.assertIn('подтвержден',answer.lower().replace('ё','е'))
                        self.assertEqual(history,original)
                        self.assertTrue(context_budget._summaries)
                    finally:
                        timer.cancel();llm.unload_model();native.close()

    def test_real_tools_and_persistence(self):
        records=[]
        for filename in os.environ['XOPILOT_TEST_MODELS'].split(','):
            with self.subTest(model=filename), tempfile.TemporaryDirectory(prefix='xopilot-real-tools-') as folder:
                native=db.advanced_xopilot.PyDatabase(str(Path(folder)/'qa.db'),key='41'*32)
                with patch.object(db,'_db',native), patch.dict(os.environ, XDG_DATA_HOME=folder):
                    native.set_setting('inference_backend','gpu')
                    workspace=workspaces.create_workspace('Проверка инструментов')
                    chat=native.create_chat('Задача')
                    workspaces.assign_chat(chat,workspace['id'])
                    library.append_materials(workspace['id'],[library.add_note('Бюджет Орион','Бюджет проекта Орион: 593 рублей.')])
                    project=Path(folder)/'project';project.mkdir()
                    (project/'main.py').write_text('print(0)\n')
                    project_tools.configure(workspace['id'],str(project))
                    events=[];approvals=[];calls=[]
                    cancel=threading.Event();timer=threading.Timer(240,cancel.set)
                    timer.start();started=time.monotonic()
                    record=dict(model=filename,passed=False)
                    records.append(record)
                    def generate(prompt,**kwargs):
                        raw=llm.generate_reply(prompt,**kwargs)
                        calls.append(raw)
                        print('MODEL',filename,'REPLY',raw,flush=True)
                        return raw
                    def approve(request):
                        approvals.append(request)
                        # Explicitly approve only writes to the test file and the
                        # requested Python print command. Never approve desktop input.
                        if request['kind']=='file':return Path(request['path']).name=='main.py'
                        return request['kind']=='command' and request['argv']==[sys.executable,'main.py']
                    try:
                        llm.load_model(filename)
                        self.assertEqual(llm.execution_info()['backend'],'gpu')
                        answer=run_agent('Найди бюджет проекта Орион в библиотеке и создай Canvas с названием «Бюджет» с найденной суммой.',
                            chat_id=chat,history=[],attachments=[],instructions='',level='high',cancelled=cancel,
                            generate=generate,on_action=events.append,approve=approve)
                        docs=canvases.list_documents(chat)
                        self.assertTrue(any('593' in d['content'] for d in docs),answer)
                        answer2=run_agent('Прочитай main.py в подключённой папке. Замени вывод на print(6 * 7), сохрани main.py и выполни команду '+
                            json.dumps([sys.executable,'main.py'])+'. Сообщи фактический вывод.',
                            chat_id=chat,history=[],attachments=[],instructions='',level='high',cancelled=cancel,
                            generate=generate,on_action=events.append,approve=approve)
                        self.assertIn('6', (project/'main.py').read_text())
                        results=[e for e in events if e['tool']=='run_project_command' and e['phase']=='result']
                        self.assertTrue(results,answer2)
                        self.assertEqual(results[-1]['result']['exit_code'],0)
                        self.assertEqual(results[-1]['result']['output'].strip(),'42')
                        self.assertTrue(any(a['kind']=='file' for a in approvals))
                        self.assertTrue(any(a['kind']=='command' for a in approvals))
                        record['passed']=True
                    except BaseException as exc:
                        record['error']=str(exc)
                        raise
                    finally:
                        record.update(seconds=round(time.monotonic()-started,2),
                            backend=llm.execution_info()['backend'],replies=calls,events=events)
                        timer.cancel();llm.unload_model();native.close()
                        if os.environ.get('XOPILOT_MODEL_REPORT'):
                            Path(os.environ['XOPILOT_MODEL_REPORT']).write_text(json.dumps(records,ensure_ascii=False,indent=2))
