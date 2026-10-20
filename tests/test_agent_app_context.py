"""
Файл: /tests/test_agent_app_context.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Проверяю контекст внешнего приложения, настоящий импорт поиска и защиту от выдуманных результатов.
          Исполнитель: Codex. Системные действия подменены, личные чаты не используются.
"""
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from App.services import db,agent,agent_context


class ContextRoutingTests(unittest.TestCase):
    def test_telegram_followup_is_an_app_action_not_xopilot_history(self):
        history=[{'role':'user','content':'окей открой телеграмм'},
                 {'role':'ai','content':'Telegram открыт.'}]
        self.assertTrue(agent.needs_tools('хм да открой мне чат Ваня а',history))
        self.assertIn('телеграм',agent_context.external_app('открой мне чат Ваня',history))
        history.append({'role':'user','content':'открой мне чат Ваня'})
        self.assertTrue(agent.needs_tools('в телеграмми',history))
        self.assertFalse(agent.needs_tools('как открыть чат в Telegram?',history))
        self.assertFalse(agent.needs_tools('спасибо',history))
        self.assertIsNone(agent_context.external_app('Найди в предыдущем чате ссылку',history))
        self.assertIsNone(agent_context.external_app('Найди чат Xopilot',history))
        self.assertIsNone(agent_context.external_app('Найди в прошлом чате Xopilot обсуждение Telegram',history))

    def test_old_tool_details_do_not_pollute_next_turn_or_mutate_saved_record(self):
        from App.app.tasks.task_summaries import PREFIX,context
        record=dict(tool='list_apps',label='Список приложений',title='',state='Готово',summary='Найдено: 105',
                    links=[],arguments_text='{}',detail='OLD_PRIVATE_DETAIL_'*1000)
        saved=PREFIX+json.dumps(record,ensure_ascii=False)
        digest=context(saved)
        self.assertIn('list_apps',digest);self.assertIn('105',digest)
        self.assertNotIn('OLD_PRIVATE_DETAIL',digest)
        self.assertLess(len(digest),400)
        self.assertIn('OLD_PRIVATE_DETAIL',saved)
        self.assertEqual(context('Обычный ответ'),'Обычный ответ')

    def test_packaged_search_and_read_use_actual_database_without_App_prefix(self):
        script=r'''
import sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path.cwd()/'App'))
from services import db,chat_search
with tempfile.TemporaryDirectory() as folder, db.advanced_xopilot.PyDatabase(str(Path(folder)/'qa.db'),key='cc'*32) as native:
 with patch.object(db,'_db',native):
  cid=native.create_chat('Atlas')
  native.add_message(cid,'user','Ваня использует порт 7791')
  found=chat_search.search('Ваня')
  assert found['chats'][0]['chat_id']==cid
  assert '7791' in found['chats'][0]['matches'][0]['excerpt']
  assert '7791' in chat_search.read(cid,query='Ваня')['messages'][0]['content']
'''
        result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


@unittest.skipIf(db.advanced_xopilot is None,'Native DB required')
class AgentRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.native=db.advanced_xopilot.PyDatabase(str(Path(self.temp.name)/'qa.db'),key='ca'*32)
        self.addCleanup(self.native.close)
        p=patch.object(db,'_db',self.native);p.start();self.addCleanup(p.stop)
        self.cid=self.native.create_chat('QA')

    def run_agent(self,generate,prompt='Открой чат Ваня в Telegram',history=()):
        return agent.run_agent(prompt,chat_id=self.cid,history=list(history),attachments=[],instructions='',level='auto',network=True,cancelled=threading.Event(),generate=generate,on_action=lambda _:None)

    def test_discovery_routes_messenger_chat_to_desktop_and_blocks_private_history_search(self):
        replies=iter([{'tool':'discover_tools','arguments':{'query':'chats переписки'}},
                      {'tool':'search_chats','arguments':{'query':'Ваня'}},
                      {'final':'Управление окном недоступно, откройте чат вручную.','needs_input':True}])
        schemas=[]
        def generate(*_args,**kwargs):
            schemas.append({t['function']['name'] for t in kwargs['native_tools']})
            self.assertIn('внешнему приложению',kwargs['native_instructions'])
            return json.dumps(next(replies),ensure_ascii=False)
        with patch('App.services.desktop_control.supported',return_value=True),patch.object(agent.chat_search,'search') as search:
            answer=self.run_agent(generate)
        search.assert_not_called()
        self.assertIn('computer_view',schemas[1]);self.assertNotIn('search_chats',schemas[1])
        self.assertIn('недоступно',answer)

    def test_fabricated_screenshot_is_repaired_without_claiming_it_was_captured(self):
        count=0
        def generate(*_args,**_kwargs):
            nonlocal count
            count+=1
            return json.dumps({'final':'Результат инструмента (данные): Экран монитора xopilot://image/fake.png'} if count==1 else
                              {'final':'Не удалось получить экран. Нужен доступ к компьютеру.','needs_input':True},ensure_ascii=False)
        answer=self.run_agent(generate,prompt='в телеграмми',history=[{'role':'user','content':'Открой чат Ваня'}])
        self.assertNotIn('xopilot://',answer);self.assertEqual(count,2)

    def test_repeated_structural_error_is_not_reexecuted_with_different_query(self):
        count=0
        def generate(*_args,**_kwargs):
            nonlocal count
            count+=1
            return json.dumps({'tool':'search_chats','arguments':{'query':'Ваня '+str(count)}})
        with patch.object(agent.chat_search,'search',side_effect=ImportError('broken import')) as search:
            with self.assertRaisesRegex(RuntimeError,'сломанного инструмента'):
                self.run_agent(generate,prompt='Найди чат Xopilot')
        search.assert_called_once();self.assertEqual(count,3)

    def test_user_can_change_target_from_telegram_to_xopilot_during_task(self):
        class Task:
            changed=False
            def checkpoint(self):pass
            def generate(self,generate,current,*,network,on_updates,**options):
                if not self.changed:
                    self.changed=True
                    current,options=on_updates([{'text':'Нет, найди чат Xopilot','attachments':[]}],options)
                return generate(current,**options)
        replies=iter([{'tool':'discover_tools','arguments':{'query':'chats'}},
                      {'tool':'search_chats','arguments':{'query':'Atlas'}},
                      {'final':'В истории Xopilot совпадений нет.'}])
        def generate(*_args,**options):
            self.assertNotIn('Текущая задача относится к внешнему приложению',options['native_instructions'])
            return json.dumps(next(replies),ensure_ascii=False)
        with patch.object(agent.chat_search,'search',wraps=agent.chat_search.search) as search:
            answer=agent.run_agent('Открой чат в Telegram',chat_id=self.cid,history=[],attachments=[],instructions='',level='auto',network=True,cancelled=threading.Event(),generate=generate,task=Task(),on_action=lambda _:None)
        search.assert_called_once_with('Atlas',after_chat_id=0)
        self.assertIn('Xopilot',answer)
