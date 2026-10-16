"""Final account/chat/inline-call regressions, including persistent activity."""
import json
import tempfile
import unittest
import flet as ft
from pathlib import Path
from unittest.mock import Mock, patch
from App.services import chat_store
from App.services.db import advanced_xopilot
from App.settings.account import sync as sync_ui
from App.settings.history import list as history_ui
from App.app.voice.live_conversation import LiveConversation


class EmptyChatTests(unittest.TestCase):
    def test_real_database_drafts_messages_canvas_and_deleted_chat(self):
        with tempfile.TemporaryDirectory() as folder, advanced_xopilot.PyDatabase(str(Path(folder)/'test.db')) as db:
            with patch.object(chat_store,'get_db',return_value=db):
                cid=db.create_chat('Новый чат')
                self.assertTrue(chat_store.chat_is_unused(cid))
                db.set_setting(f'draft:{cid}',json.dumps({'text':'draft','files':[]}))
                self.assertFalse(chat_store.chat_is_unused(cid))
                db.set_setting(f'draft:{cid}',json.dumps({'text':'','files':[['file','/path']]}))
                self.assertFalse(chat_store.chat_is_unused(cid))
                db.set_setting(f'draft:{cid}','{}')
                db.set_setting('canvases_v1',json.dumps([{'chat_id':cid,'content':''}]))
                self.assertFalse(chat_store.chat_is_unused(cid))
                db.set_setting('canvases_v1','[]')
                message=db.add_message(cid,'user','hello')
                self.assertFalse(chat_store.chat_is_unused(cid))
                db.delete_message(message)
                self.assertTrue(chat_store.chat_is_unused(cid))
                db.delete_chat(cid)
                self.assertFalse(chat_store.chat_is_unused(cid))
                self.assertFalse(chat_store.chat_is_unused(-1))


class SyncToggleTests(unittest.IsolatedAsyncioTestCase):
    async def test_enable_with_saved_key_starts_transfer_and_busy_does_not_refresh_chat(self):
        page=Mock()
        options=dict(sync_ui.sync.DEFAULTS)
        with patch.object(sync_ui.sync,'options',side_effect=lambda:dict(options)), \
                patch.object(sync_ui.sync,'save_options',side_effect=lambda values:options.update(values)), \
                patch.object(sync_ui.sync,'status',return_value={}), \
                patch.object(sync_ui.sync,'owner',return_value='test-owner'), \
                patch.object(sync_ui.sync,'key_ready',return_value=True), \
                patch.object(sync_ui.sync,'conflict_items',return_value={}), \
                patch.object(sync_ui.cloud_traffic,'usage',return_value=0), \
                patch.object(sync_ui.sync,'run',return_value={'busy':True}) as transfer:
            sync_ui.open_sync(page)
            dialog=page.show_dialog.call_args.args[0]
            toggle=dialog.content.controls[0]
            toggle.value=True;toggle.on_change(None)
            function,*arguments=page.run_task.call_args.args
            await function(*arguments)
            self.assertTrue(options['enabled'])
            transfer.assert_called_once()
            page._xopilot_sync_refresh.assert_not_called()
            self.assertTrue(any('уже выполняется' in (getattr(control,'value',None) or '')
                                for control in dialog.content.controls if isinstance(control,ft.Text)))

    async def test_enable_guides_setup_then_persists_enabled_only_after_success(self):
        page=Mock()
        options=dict(sync_ui.sync.DEFAULTS)
        ready=False
        def setup(*args):
            nonlocal ready
            ready=True
        def save(values):options.update(values)
        with patch.object(sync_ui.sync,'options',side_effect=lambda:dict(options)), \
             patch.object(sync_ui.sync,'status',return_value={}), \
             patch.object(sync_ui.sync,'owner',return_value='test-owner'), \
             patch.object(sync_ui.sync,'key_ready',side_effect=lambda:ready), \
             patch.object(sync_ui.sync,'conflict_items',return_value={}), \
             patch.object(sync_ui.cloud_traffic,'usage',return_value=0), \
             patch.object(sync_ui.sync,'setup',side_effect=setup), \
             patch.object(sync_ui.sync,'save_options',side_effect=save):
            sync_ui.open_sync(page)
            dialog=page.show_dialog.call_args.args[0]
            toggle=dialog.content.controls[0]
            toggle.value=True;toggle.on_change(None)
            self.assertFalse(toggle.value)
            self.assertFalse(options['enabled'])
            password_dialog=page.show_dialog.call_args.args[0]
            password_dialog.content.controls[1].value='Synthetic test password'
            password_dialog.content.controls[2].value='Synthetic test password'
            await password_dialog.actions[1].on_click(None)
            self.assertTrue(options['enabled'])
            self.assertTrue(toggle.value)
            self.assertFalse(dialog.actions[1].disabled)
            toggle.value=False;toggle.on_change(None)
            self.assertFalse(options['enabled'])

    async def test_failed_password_keeps_sync_disabled_and_dialog_open(self):
        page=Mock()
        with patch.object(sync_ui.sync,'options',return_value=dict(sync_ui.sync.DEFAULTS)), \
             patch.object(sync_ui.sync,'status',return_value={}), \
             patch.object(sync_ui.sync,'owner',return_value='test-owner'), \
             patch.object(sync_ui.sync,'key_ready',return_value=False), \
             patch.object(sync_ui.sync,'conflict_items',return_value={}), \
             patch.object(sync_ui.cloud_traffic,'usage',return_value=0), \
             patch.object(sync_ui.sync,'setup',side_effect=ValueError('Пароли не совпадают')), \
             patch.object(sync_ui.sync,'save_options') as save:
            sync_ui.open_sync(page)
            toggle=page.show_dialog.call_args.args[0].content.controls[0]
            toggle.value=True;toggle.on_change(None)
            dialog=page.show_dialog.call_args.args[0]
            await dialog.actions[1].on_click(None)
            self.assertFalse(toggle.value)
            self.assertIn('не совпадают',dialog.content.controls[-1].value)
            save.assert_not_called();page.pop_dialog.assert_not_called()


class HistoryTests(unittest.TestCase):
    def test_individual_delete_removes_selected_row_only(self):
        page=Mock(width=900,height=700)
        delete=Mock(return_value=True)
        with patch.object(history_ui,'list_chat_items',return_value=[(1,'First','',False),(2,'Second','',False)]), \
             patch.object(history_ui,'load_chat_messages',return_value=[]), \
             patch.object(history_ui,'chat_workspace',return_value={'name':'All'}):
            view=history_ui.build_history_list(page,on_delete=delete)
            rows=view.controls[2]
            rows.controls[0].content.controls[-2].on_click(None)
            delete.assert_not_called()
            confirmation=page.show_dialog.call_args.args[0]
            confirmation.actions[-1].on_click(None)
            delete.assert_called_once_with(1)
            self.assertEqual(len(rows.controls),1)
            self.assertEqual(rows.controls[0].content.controls[1].controls[0].value,'Second')


    def test_history_delete_persists_only_selected_chat_and_keeps_other_messages(self):
        with tempfile.TemporaryDirectory() as folder, advanced_xopilot.PyDatabase(str(Path(folder)/'test.db')) as db:
            first=db.create_chat('First');second=db.create_chat('Second')
            db.add_message(first,'user','Remove this')
            db.add_message(second,'user','Keep this')
            page=Mock(width=900,height=700)
            with patch.object(chat_store,'get_db',return_value=db), \
                 patch.object(history_ui,'chat_workspace',return_value={'name':'All'}):
                view=history_ui.build_history_list(page,on_delete=chat_store.delete_chat)
                rows=view.controls[2]
                selected=next(row for row in rows.controls if row.content.controls[1].controls[0].value=='First')
                selected.content.controls[-2].on_click(None)
                page.show_dialog.call_args.args[0].actions[-1].on_click(None)
                self.assertEqual([row[0] for row in db.list_chats()],[second])
                self.assertEqual(db.get_messages(second)[0].content,'Keep this')
                self.assertEqual(db.get_messages(first),[])


class InlineCallTests(unittest.IsolatedAsyncioTestCase):
    async def test_open_and_close_use_inline_controls_no_live_dialog(self):
        page=Mock(web=True)
        live=LiveConversation(page,lambda:False,lambda:[],Mock(),Mock())
        await live.open_call()
        self.assertTrue(live.status.visible)
        self.assertIn(live.camera_button,live.status.controls[1].controls)
        self.assertIn(live.screen_button,live.status.controls[1].controls)
        page.show_dialog.assert_not_called()
        await live.end_call()
        self.assertFalse(live.status.visible)
        page.pop_dialog.assert_not_called()

# Exercise the actual composer callback, rather than just the call widget.
import test_real_answers
from unittest.mock import AsyncMock
from App.app import main as main_ui


class FinalComposerTests(unittest.IsolatedAsyncioTestCase):
    setUp = test_real_answers.PersistenceUITests.setUp

    async def test_typed_live_question_uses_main_composer_without_ordinary_generation(self):
        live=self.prompt_container.call_args.kwargs['live_button'].on_click.__self__
        live._state='listening'
        asked=[]
        def accept():
            asked.append(live.frame_question.value)
            return True
        live.ask_frame=AsyncMock(side_effect=accept)
        self.prompt_container.call_args.kwargs['attachments'].update=Mock()
        self.prompt.value='Вопрос во время звонка'
        await self.send(None)
        live.ask_frame.assert_awaited_once()
        self.assertEqual(asked,['Вопрос во время звонка'])
        self.assertIs(live.frame_question,self.prompt)
        self.assertEqual(self.prompt.value,'')
        self.generate.assert_not_called()
        self.save.assert_not_called()

    async def test_rejected_live_question_keeps_draft_and_shows_error(self):
        live=self.prompt_container.call_args.kwargs['live_button'].on_click.__self__
        live._state='listening'
        live.frame_question.error_text='Дождитесь отправки предыдущего вопроса'
        live.ask_frame=AsyncMock(return_value=False)
        self.prompt.value='Не терять этот вопрос'
        await self.send(None)
        self.assertEqual(self.prompt.value,'Не терять этот вопрос')
        self.assertIn('Дождитесь',live.status_text.value)
        self.generate.assert_not_called()

    async def test_unused_current_chat_is_reused_and_draft_forces_new_chat(self):
        new=self.menu.call_args.kwargs['on_new_chat_click']
        with patch.object(main_ui,'chat_is_unused',return_value=True), \
             patch.object(main_ui,'create_new_chat',return_value=2) as create, \
             patch.object(main_ui.workspaces,'assign_chat') as assign, \
             patch.object(main_ui.workspaces,'selected_workspace',return_value='all'):
            new()
            create.assert_not_called()
            assign.assert_called_with(1,'all')
            self.prompt.value='Незавершённый текст'
            new()
            create.assert_called_once()
            assign.assert_called_with(2,'all')
