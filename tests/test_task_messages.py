"""
Файл: /tests/test_task_messages.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Журнал команд в чате и запрет управления процессом другого чата.
          Исполнитель проверок: Codex.
"""
import sys
import tempfile
import unittest
from unittest.mock import Mock
from App.app.task_messages import TaskMessages,code_block
from App.services import task_processes
from App.app.task_summaries import decode,summarize


class MessageTests(unittest.IsolatedAsyncioTestCase):
    async def test_action_updates_one_message_and_saves_command_output(self):
        page=Mock();chat=Mock(controls=[]);save=Mock(return_value=17);update=Mock()
        journal=TaskMessages(page,1,'project',current_chat=lambda:1,chat_list=chat,save=save,update=update)
        event=dict(id='action1',tool='run_project_command',label='Команда',arguments={'argv':['python','-c','print(42)']},phase='start')
        await journal.receive(event)
        self.assertEqual(len(chat.controls),1);save.assert_not_called()
        await journal.receive({**event,'phase':'result','result':{'pid':42,'id':'process','running':False,
            'exit_code':0,'cwd':'/project','output':'42\n'}})
        self.assertEqual(len(chat.controls),1)
        self.assertIn('print(42)',save.call_args.args[1]);self.assertIn('код 0',save.call_args.args[1])
        record=decode(save.call_args.args[1])
        self.assertIn('42\n',record['detail']);self.assertFalse(journal.items['action1']['stop'].visible)
        self.assertFalse(chat.controls[0].content.controls[0].expanded)
        restored=journal.restore_saved(record,17)
        self.assertEqual(restored.data,17)
        self.assertFalse(restored.content.controls[0].expanded)

    async def test_stop_message_cannot_control_another_chats_process(self):
        with tempfile.TemporaryDirectory() as folder:
            process=task_processes.start('chat:2','project',[sys.executable,'-c','import time;time.sleep(30)'],folder)
            try:
                page=Mock();journal=TaskMessages(page,1,'project',current_chat=lambda:1,chat_list=Mock(controls=[]),save=Mock(),update=Mock())
                await journal.stop({'event':{'result':process}})
                self.assertTrue(task_processes.get(process['id'],'chat:2','project').snapshot()['running'])
                page.show_dialog.assert_called_once()
            finally:task_processes.get(process['id'],'chat:2','project').stop()

    async def test_running_command_can_be_restored_and_stopped_from_its_chat(self):
        with tempfile.TemporaryDirectory() as folder:
            process=task_processes.start('chat:1','project',[sys.executable,'-c','import time;time.sleep(30)'],folder)
            try:
                page=Mock();update=Mock();view=Mock(controls=[])
                journal=TaskMessages(page,1,'project',current_chat=lambda:1,chat_list=lambda:view,save=Mock(),update=update)
                event=dict(id=process['id'],tool='run_project_command',label='Команда',arguments={'argv':process['argv']},phase='result',result=process)
                card=journal.restore(event,17)
                self.assertEqual(card.data,17)
                item=journal.make_item(event);item['message_id']=17
                await journal.stop(item)
                self.assertFalse(task_processes.get(process['id'],'chat:1','project').snapshot()['running'])
                update.assert_called_once();self.assertEqual(update.call_args.args[0],17)
            finally:task_processes.get(process['id'],'chat:1','project').stop()

    def test_output_cannot_close_its_markdown_code_block(self):
        value='first\n```\n# not a heading\n````\nlast'
        self.assertTrue(code_block(value).startswith('`````\n'))
        self.assertTrue(code_block(value).endswith('\n`````'))

    def test_chat_search_summary_contains_found_title_and_site_link(self):
        text,links=summarize('search_chats',{'chats':[{'title':'У меня есть сайт','matches':[{'excerpt':'Мой сайт https://xopilot.by.'}]}]})
        self.assertIn('У меня есть сайт',text)
        self.assertEqual(links,['https://xopilot.by'])
