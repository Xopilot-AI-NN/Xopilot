"""New catalog, persisted icons/titles, and real HTTP transport contracts."""
import json
import threading
import unittest
from concurrent.futures import CancelledError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch, Mock
import flet as ft
from App.services import api_chat, chat_store, workspaces
from App.services.agent import run_agent
from App.app import palette
import test_canvas_library_agent as native_fixture


class CatalogPersistenceTests(unittest.TestCase):
    setUp = native_fixture.DocumentWorkflowTests.setUp
    # Inherit a native isolated DB fixture, not the test cases themselves.
    def test_project_icon_survives_edit_and_reopen(self):
        item = workspaces.create_workspace('Код', icon='code')
        workspaces.update_workspace(item['id'], 'Переименован')
        self.assertEqual(next(w for w in workspaces.list_workspaces() if w['id'] == item['id'])['icon'], 'code')
        with self.assertRaises(ValueError):
            workspaces.update_workspace(item['id'], 'Ошибка', icon='unknown')
        self.assertEqual(next(w for w in workspaces.list_workspaces() if w['id'] == item['id'])['name'], 'Переименован')

    def test_chat_title_uses_first_question_and_keeps_manual_names(self):
        with patch.object(chat_store, 'get_db', side_effect=lambda: self.db):
            chat = self.db.create_chat('Новый чат')
            chat_store.save_user_message(chat, 'Помоги  написать\nкод проекта ОРИОН')
            self.assertEqual(chat_store.auto_name_chat(chat), 'Помоги написать код проекта ОРИОН')
            chat_store.rename_chat(chat, 'Моё название')
            chat_store.save_user_message(chat, 'Новая тема')
            self.assertEqual(chat_store.auto_name_chat(chat), 'Моё название')

    def test_existing_unnamed_chats_are_named_from_history(self):
        with patch.object(chat_store, 'get_db', side_effect=lambda: self.db):
            chat = self.db.create_chat('Новый чат')
            self.db.add_message(chat, 'user', 'Старый вопрос', None, None, [])
            titles = dict((cid, title) for cid, title, _, _ in chat_store.list_chat_items())
            self.assertEqual(titles[chat], 'Старый вопрос')

    def test_api_configuration_reopens_without_plaintext_key_on_disk(self):
        with patch.object(api_chat, 'get_db', side_effect=lambda: self.db), \
             patch.object(api_chat, 'get_setting', side_effect=lambda key, default=None: self.db.get_setting(key) or default):
            api_chat.save_configuration({'url':'https://api.example/v1', 'model':'model-id', 'key':'qa-key-only-1234'})
            api_chat.select_api()
            self.db = None
            self.db = native_fixture.advanced_xopilot.PyDatabase(str(self.db_path))
            self.assertTrue(api_chat.is_api_selected())
            self.assertEqual(api_chat.configuration()['key'], 'qa-key-only-1234')
            self.assertNotIn(b'qa-key-only-1234', self.db_path.read_bytes())

    def test_agent_resolves_canvas_title_but_rejects_ambiguous_names(self):
        from App.services import canvases
        from App.services.agent import LocalTools
        doc = canvases.create_document('Итог', content='249 рублей', chat_id=self.chat, workspace_id=self.workspace['id'])
        tools = LocalTools(self.chat, threading.Event())
        result, _ = tools.call('read_canvas', {'id':'Итог'})
        self.assertEqual(result['id'], doc['id'])
        canvases.create_document('Итог', content='Другой', chat_id=self.chat, workspace_id=self.workspace['id'])
        with self.assertRaises(ValueError):
            tools.call('read_canvas', {'id':'Итог'})
        result, _ = tools.call('read_canvas', {'id':doc['id']})
        self.assertEqual(result['content'], '249 рублей')

    def test_auto_agent_extends_steps_only_when_needed(self):
        generator = Mock(side_effect=[json.dumps({'tool':'list_library','arguments':{}})]*4 + [json.dumps({'final':'Готово'})])
        result = run_agent('Выполни задачу', chat_id=self.chat, history=[], attachments=[], instructions='',
            level='auto', cancelled=threading.Event(), generate=generator)
        self.assertEqual(generator.call_count, 5)
        self.assertEqual(result.count('Список библиотеки · выполнено'), 4)


class ApiTransportTests(unittest.TestCase):
    def test_api_http_transmits_full_history_and_attachments(self):
        received = {}
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received['path'] = self.path
                received['auth'] = self.headers.get('Authorization')
                received['json'] = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'choices':[{'message':{'content':'Ответ транспорта'}}]}).encode())
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            config = {'url':f'http://127.0.0.1:{server.server_port}/v1', 'model':'qa-model', 'key':'test-only'}
            with patch.object(api_chat, 'configuration', return_value=config), patch.object(api_chat, 'record_generation'), \
                 patch.object(api_chat, 'build_attachment_message_parts', return_value=(['Факт из файла'], [])):
                answer = api_chat.generate_reply('Вопрос', history=[{'role':'user','content':'Первый'},{'role':'ai','content':'Второй'}], instructions='Инструкция')
            self.assertEqual(answer, 'Ответ транспорта')
            self.assertEqual(received['path'], '/v1/chat/completions')
            self.assertEqual(received['auth'], 'Bearer test-only')
            self.assertIn('Факт из файла', received['json']['messages'][-1]['content'])
            self.assertEqual(received['json']['messages'][2]['role'], 'assistant')
            self.assertNotIn('max_tokens', received['json'])
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_cancel_interrupts_waiting_http_body(self):
        headers_sent = threading.Event()
        release = threading.Event()
        cancelled = threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200)
                self.send_header('Content-Length', '100')
                self.end_headers()
                headers_sent.set()
                release.wait(5)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        serving = threading.Thread(target=server.serve_forever, daemon=True)
        serving.start()
        outcomes = []
        config = {'url':f'http://127.0.0.1:{server.server_port}/v1','model':'m'}
        def request():
            try:
                api_chat.generate_reply('Вопрос', cancelled=cancelled)
            except BaseException as exc:
                outcomes.append(exc)
        try:
            with patch.object(api_chat, 'configuration', return_value=config):
                worker = threading.Thread(target=request, daemon=True)
                worker.start()
                self.assertTrue(headers_sent.wait(2))
                cancelled.set()
                worker.join(2)
                self.assertFalse(worker.is_alive(), 'Cancel must release a stalled HTTP response')
                self.assertIsInstance(outcomes[0], CancelledError)
        finally:
            release.set(); server.shutdown(); server.server_close(); serving.join()

    def test_api_validation_and_pre_cancel(self):
        for url in ['http://remote.example/v1', 'https://user:password@example.com/v1', 'https://example.com/v1?key=secret']:
            with self.assertRaises(ValueError):
                api_chat.validate_configuration({'url':url,'model':'m'})
        cancelled = threading.Event(); cancelled.set()
        with patch.object(api_chat, 'configuration', return_value={'url':'http://localhost/v1','model':'m'}):
            with self.assertRaises(CancelledError):
                api_chat.generate_reply('Вопрос', cancelled=cancelled)

    def test_dropdown_uses_input_surface_and_rounded_menu(self):
        obj = palette.apply_palette(ft.Dropdown(options=[ft.DropdownOption(key='a', text='A')]))
        self.assertEqual(obj.menu_style.shape.radius, 16)
        self.assertEqual(obj.menu_style.bgcolor, obj.bgcolor)
        self.assertEqual(obj.options[0].style.shape.radius, 12)
