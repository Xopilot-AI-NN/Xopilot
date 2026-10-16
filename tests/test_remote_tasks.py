"""
Файл: /tests/test_remote_tasks.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Диагностика отсутствующего сервера и завершение фонового приёма заданий.
          Исполнитель: Codex.
"""
import threading
import unittest
from unittest.mock import Mock,patch
from App.services import remote_tasks as remote


class RemoteTests(unittest.TestCase):
    def test_workspace_remote_continues_the_synced_chat_without_duplicate_user_message(self):
        import json
        from contextlib import ExitStack
        from App.services import agent,chat_store,api_chat
        class Reply(str):files=[]
        db=Mock();db.get_setting.return_value=json.dumps({'records':{'chat:uuid':{'scope':'chats','local_id':9}}})
        db.sync_chat_snapshot.return_value=json.dumps({'messages':[{'role':'user','content':'First'},
            {'role':'ai','content':'Previous answer'},{'role':'user','content':'Next'}]})
        task={'version':1,'id':'job','sender':'phone','target':'pc','workspace_id':'project','chat_uuid':'uuid','prompt':'Next'}
        with ExitStack() as stack:
            stack.enter_context(patch.object(remote,'credentials',return_value=({'account_id':'owner','session_id':'pc'},b'x'*32)))
            stack.enter_context(patch.object(remote,'decode',return_value=task))
            stack.enter_context(patch.object(remote,'get_db',return_value=db))
            stack.enter_context(patch.object(remote.workspaces,'list_workspaces',return_value=[{'id':'project'}]))
            stack.enter_context(patch.object(remote.workspaces,'chat_workspace',return_value={'id':'project'}))
            stack.enter_context(patch.object(remote.workspaces,'chat_resources',return_value=('',[])))
            stack.enter_context(patch.object(remote.cloud_sync,'run'))
            stack.enter_context(patch.object(remote.cloud_sync,'options',return_value={'enabled':True}))
            stack.enter_context(patch.object(api_chat,'is_api_selected',return_value=True))
            generate=stack.enter_context(patch.object(agent,'run_agent',return_value=Reply('Done')))
            save_user=stack.enter_context(patch.object(chat_store,'save_user_message'))
            stack.enter_context(patch.object(chat_store,'save_ai_message'))
            stack.enter_context(patch.object(remote,'_result'))
            remote._execute({'id':'job','sender':'phone','task':'encrypted'},threading.Event())
            db.create_chat.assert_not_called();save_user.assert_not_called()
            self.assertEqual(generate.call_args.kwargs['chat_id'],9)
            self.assertEqual(generate.call_args.kwargs['history'][-1]['content'],'Previous answer')

    def test_pair_request_does_not_grant_access_and_heartbeat_is_authoritative(self):
        account={'account_id':'owner','session_id':'pc'}
        db=Mock()
        with patch.object(remote,'credentials',return_value=(account,b'x'*32)),patch.object(remote,'get_db',return_value=db),\
             patch.object(remote,'is_android',return_value=False),patch.object(remote.cloud,'request',return_value={'enabled':True,'senders':[]}) as request:
            remote.request_pair('pc')
            request.assert_called_once_with('/remote/pairings',method='POST',body={'target':'pc'})
            db.set_setting.assert_not_called()
            remote.announce()
            self.assertIn('"senders": []',db.set_setting.call_args.args[1])

    def test_pc_mode_is_only_available_in_normal_workspace_chats(self):
        from App.app.workspace.workspace_remote import WorkspaceRemote
        page=Mock();chat=[1];workspace=['all']
        controller=WorkspaceRemote(page,lambda:chat[0],lambda:workspace[0],Mock(),Mock(),Mock(),Mock())
        with patch('App.app.workspace.workspace_remote.is_android',return_value=True):
            self.assertFalse(controller.eligible)
            workspace[0]='project';self.assertTrue(controller.eligible)
            chat[0]=-1;self.assertFalse(controller.eligible)
        chat[0]=1
        with patch('App.app.workspace.workspace_remote.is_android',return_value=False):self.assertFalse(controller.eligible)

    def test_missing_server_route_is_explained_without_exposing_credentials(self):
        from App.services.cloud_account import CloudError
        with patch.object(remote,'credentials'),patch.object(remote.cloud,'request',side_effect=CloudError('server_error',404)):
            with self.assertRaisesRegex(ValueError,'обновление серверной части'):remote.hosts()

    def test_shutdown_cancels_active_task_and_stops_polling(self):
        cancelled=threading.Event();stop=threading.Event();thread=Mock()
        with patch.object(remote,'_cancel',cancelled),patch.object(remote,'_stop',stop),patch.object(remote,'_thread',thread):
            remote.shutdown()
        self.assertTrue(cancelled.is_set());self.assertTrue(stop.is_set());thread.join.assert_called_once_with(timeout=5)

    def test_key_missing_cannot_request_remote_host(self):
        with patch.object(remote.cloud,'state',return_value={'account_id':'qa'}),patch.object(remote,'get_db') as db,patch.object(remote.cloud,'request') as request:
            db.return_value.get_setting.return_value=None
            with self.assertRaisesRegex(ValueError,'пароль'):remote.hosts()
            request.assert_not_called()

    def test_remote_computer_approval_does_not_require_file_diff_fields(self):
        from App.app.browser.remote_browser import approval_content
        for kind in ('device','computer_session'):
            title,preview=approval_content({'kind':kind,'title':'Кнопка QA','arguments':{'action':'click','target':'id'}})
            self.assertEqual(title,'Кнопка QA');self.assertIn('click',preview)

    def test_lost_submit_reply_reuses_exact_encrypted_operation(self):
        import json
        from App.services.cloud_account import CloudError
        values={}
        db=Mock();db.get_setting.side_effect=lambda key:values.get(key)
        db.set_setting.side_effect=lambda key,value:values.__setitem__(key,value)
        account={'session_id':'phone','account_id':'owner'}
        with patch.object(remote,'get_db',return_value=db),patch.object(remote,'credentials',return_value=(account,b'x'*32)),patch.object(remote.cloud,'request',side_effect=[CloudError('connection_failed'),{'ok':True}]) as request:
            with self.assertRaises(remote.DeliveryPending) as pending:remote.submit('pc','Do work')
            identifier=pending.exception.identifier
            self.assertEqual(remote.pending_deliveries(),[identifier])
            first=request.call_args.kwargs['body']
            remote.retry(identifier)
            self.assertEqual(request.call_args.kwargs['body'],first)
            self.assertEqual(remote.pending_deliveries(),[])
