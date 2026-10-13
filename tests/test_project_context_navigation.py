"""Project identity, original agent objectives and explicit ordinary-chat navigation."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import flet as ft
from App.services import workspaces, agent, project_tools, canvases, db, chat_store
from App.app import main as main_ui
from App.app.buttons.brand import brand_button
from App.app import palette

class Settings:
    def __init__(self): self.data = {}
    def get_setting(self, key): return self.data.get(key)
    def set_setting(self, key, value): self.data[key] = value

class ContextTests(unittest.TestCase):
    def setUp(self):
        self.db = Settings()
        for module in (workspaces, project_tools, canvases):
            patcher = patch.object(module, 'get_db', return_value=self.db)
            patcher.start(); self.addCleanup(patcher.stop)
        self.project = workspaces.create_workspace('Test', materials=[
            {'name': 'src/main.rs', 'path': '/owned/main.rs'},
            {'name': 'disabled.txt', 'path': '/owned/off.txt', 'enabled': False},
            {'name': 'missing.txt', 'path': ''}])
        workspaces.assign_chat(1, self.project['id'])

    def test_resources_belong_to_chat_even_when_other_project_is_selected(self):
        other = workspaces.create_workspace('Other')['id']
        workspaces.select_workspace(other)
        context, files = workspaces.chat_resources(1)
        self.assertIn('Test', context);self.assertIn('src/main.rs', context)
        self.assertIn('missing.txt', context);self.assertNotIn('disabled.txt', context)
        self.assertNotIn('Other', context)
        self.assertEqual(files, [('src/main.rs', '/owned/main.rs')])
        self.assertEqual(workspaces.chat_resources(2), ('', []))
        rows = workspaces.sidebar_chats([(1, 'привет', 'Сообщений: 2', False), (2, 'Обычный', 'Сообщений: 1', False)])
        self.assertTrue(rows[0][2].startswith('Test ·'));self.assertTrue(rows[1][2].startswith('Обычный чат ·'))

    def test_retry_keeps_original_request_and_materials_in_transcript(self):
        request = 'Создай файл example.py в Canvas с функцией sum_qa'
        generation = Mock(side_effect=[json.dumps({'final': 'Готово'}), json.dumps({'tool': 'create_canvas',
            'arguments': {'title': 'example.py', 'kind': 'code', 'content': 'def sum_qa(a,b): return a+b'}}),
            json.dumps({'final': 'Сохранён example.py'})])
        context, files = workspaces.chat_resources(1)
        answer = agent.run_agent(request, chat_id=1, history=[{'role':'user','content':'привет'}],
            attachments=files, instructions=context, level='auto', cancelled=threading.Event(), generate=generation)
        self.assertIn('example.py', answer)
        self.assertEqual(generation.call_args_list[0].kwargs['attachments'], files)
        for call in generation.call_args_list:
            self.assertIn(request, call.kwargs['instructions']);self.assertIn('Test', call.kwargs['instructions'])
            self.assertEqual(call.kwargs['attachments'], files)
        self.assertIn({'role':'user','content':request}, generation.call_args_list[1].kwargs['history'])
        self.assertEqual(canvases.list_documents(1, self.project['id'])[0]['content'], 'def sum_qa(a,b): return a+b')

    def test_logo_colours_differentiate_actions_and_keep_contrast(self):
        create = brand_button(ft.Icons.ADD, 'Добавить материал')
        browse = brand_button(ft.Icons.MENU, 'Меню')
        ai = brand_button(ft.Icons.DRAW, 'Canvas')
        remove = brand_button(ft.Icons.DELETE, 'Удалить чат')
        self.assertEqual(len({tuple(b.gradient.colors) for b in (create, browse, ai, remove)}), 4)
        def luminance(hex_colour):
            rgb = [int(hex_colour[i:i+2],16)/255 for i in (1,3,5)]
            linear = [v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
            return sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))
        for theme in ('light', 'dark', 'midnight', 'ocean', 'forest', 'lavender', 'sunset'):
            palette.set_theme(Mock(controls=[create,browse,ai,remove], overlay=[]), theme)
            for button in (create,browse,ai,remove):
                for tone in button.gradient.colors:
                    pair = sorted((luminance(button.content.color), luminance(tone)))
                    self.assertGreaterEqual((pair[1]+.05)/(pair[0]+.05), 4.5)
                self.assertEqual(button.border.top.width, 1)
        palette.set_theme(Mock(controls=[create,browse,ai,remove], overlay=[]), 'light')
        filled = palette.apply_palette(ft.FilledButton(content='Удалить'))
        self.assertEqual(filled.style.bgcolor[ft.ControlState.DEFAULT], remove.gradient.colors[0])

@unittest.skipIf(db.advanced_xopilot is None, 'Native DB not built')
class NewChatNavigationTests(unittest.TestCase):
    def test_project_choice_keeps_empty_chat_then_creates_ordinary_chat_without_moving_project_history(self):
        page = Mock(width=393,height=851,web=True,services=[],_dialogs=Mock(controls=[]))
        with tempfile.TemporaryDirectory() as folder, db.advanced_xopilot.PyDatabase(str(Path(folder)/'qa.db'),key='aa'*32) as native:
            with patch.object(db,'_db',native), patch.object(chat_store,'_active_chat_id',None), \
                    patch.object(main_ui,'install_theme'), patch.object(main_ui,'get_selected_chat_model',return_value=None), \
                    patch.object(ft.TextField,'update'), patch.object(ft.ListView,'update'):
                project=workspaces.create_workspace('Test')['id']
                original=chat_store.create_new_chat();workspaces.assign_chat(original,project)
                workspaces.select_workspace(project)
                ui=main_ui.build_app_ui(page)
                header=ui.content.content.controls[0].controls[-1].content.controls[0]
                new_chat=header.content.controls[-1].items[0]
                new_chat.on_click(None)
                dialog=page.show_dialog.call_args.args[0]
                self.assertEqual(dialog.title.value,'Где создать чат?')
                dialog.content.controls[1].on_click(None)
                self.assertEqual(len(native.list_chats()),1)
                self.assertEqual(chat_store.get_or_create_active_chat_id(),original)
                native.add_message(original,'user','Сохранить в проекте')
                new_chat.on_click(None)
                page.show_dialog.call_args.args[0].content.controls[2].on_click(None)
                ordinary=chat_store.get_or_create_active_chat_id()
                self.assertNotEqual(ordinary,original)
                self.assertEqual(workspaces.chat_workspace(ordinary)['id'],'all')
                self.assertEqual(workspaces.chat_workspace(original)['id'],project)
                self.assertEqual(workspaces.selected_workspace(),'all')
                new_chat.on_click(None)
                self.assertEqual(chat_store.get_or_create_active_chat_id(),ordinary)
                self.assertEqual(len(native.list_chats()),2)
