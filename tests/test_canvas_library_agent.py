"""Persistence and actual tool execution contracts for the expanded local app."""
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from concurrent.futures import CancelledError
import flet as ft
from PIL import Image
from App.services import canvases, library, workspaces, material_store
from App.services.agent import LocalTools, run_agent
from App.services.db import advanced_xopilot
from App.app import palette


@unittest.skipIf(advanced_xopilot is None, 'Build native DB')
class DocumentWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db_path = self.root / 'test.db'
        self.db = advanced_xopilot.PyDatabase(str(self.db_path))
        self.addCleanup(lambda: setattr(self, 'db', None))
        for module in (canvases, workspaces):
            p = patch.object(module, 'get_db', side_effect=lambda: self.db)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(material_store, 'app_data_dir', return_value=self.root)
        p.start()
        self.addCleanup(p.stop)
        self.workspace = workspaces.create_workspace('Проект')
        self.chat = self.db.create_chat('Чат')
        workspaces.assign_chat(self.chat, self.workspace['id'])

    def test_text_and_drawing_survive_database_reopen_and_export(self):
        doc = canvases.create_document('План', content='Рабочий текст', chat_id=self.chat)
        doc.update(kind='drawing', strokes=[{'color': '#c94b4b', 'width': 5, 'points': [[.1,.2],[.8,.7]]}])
        canvases.save_document(doc)
        self.db = None
        self.db = advanced_xopilot.PyDatabase(str(self.db_path))
        stored = canvases.get_document(doc['id'])
        self.assertEqual(stored['content'], 'Рабочий текст')
        name, data = canvases.export_document(stored)
        self.assertEqual(name, 'План.png')
        image = Image.open(io.BytesIO(data))
        self.assertEqual(image.size, (1200, 700))
        self.assertNotEqual(image.getpixel((120,140)), (255,255,255))

    def test_folder_copies_keep_structure_and_skip_symlinks_hidden_build(self):
        folder = self.root / 'project'
        (folder/'src').mkdir(parents=True)
        (folder/'src'/'main.py').write_text('print(137)')
        (folder/'.secret.txt').write_text('private')
        (folder/'build').mkdir()
        (folder/'build'/'result.txt').write_text('skip')
        (folder/'link.txt').symlink_to(folder/'src'/'main.py')
        materials, errors = library.import_folder(folder)
        self.assertEqual(errors, [])
        self.assertEqual([m['name'] for m in materials], ['src/main.py'])
        library.append_materials(self.workspace['id'], materials)
        (folder/'src'/'main.py').unlink()
        entry = library.entries(self.workspace['id'])[0]
        self.assertTrue(entry['available'])
        self.assertIn('print(137)', library.read_entry(entry)[0])

    def test_disabled_material_is_not_given_to_chat_or_agent(self):
        note = library.add_note('Секрет', 'Не использовать')
        note['enabled'] = False
        library.append_materials(self.workspace['id'], [note])
        self.assertEqual(workspaces.chat_resources(self.chat)[1], [])
        result, _ = LocalTools(self.chat, threading.Event()).call('list_library', {})
        self.assertEqual(result, [])

    def test_search_phrase_finds_facts_spread_between_documents(self):
        library.append_materials(self.workspace['id'], [library.add_note('Бюджет', 'Бюджет ОРИОН 249 рублей'),
                                                       library.add_note('Срок', 'Срок ОРИОН 18 октября')])
        result, _ = LocalTools(self.chat, threading.Event()).call('search_library', {'query':'бюджет и срок ОРИОН'})
        self.assertEqual(len(result), 2)
        self.assertTrue(any('249' in item['excerpt'] for item in result))
        self.assertTrue(any('18 октября' in item['excerpt'] for item in result))

    def test_agent_executes_multiple_tools_and_saves_actual_document(self):
        library.append_materials(self.workspace['id'], [library.add_note('Бюджет', 'Бюджет 137 рублей')])
        generate = Mock(side_effect=[json.dumps({'tool':'search_library','arguments':{'query':'137'}}),
            json.dumps({'tool':'create_canvas','arguments':{'title':'Итог','kind':'text','content':'137 рублей'}}),
            json.dumps({'final':'Документ готов'})])
        result = run_agent('Найди бюджет и создай документ', chat_id=self.chat, history=[], attachments=[],
            instructions='', level='medium', cancelled=threading.Event(), generate=generate)
        self.assertIn('Действия агента', result)
        doc = canvases.list_documents(self.chat)[0]
        self.assertEqual(doc['content'], '137 рублей')
        self.assertIn('137', generate.call_args_list[1].args[0])
        self.assertIn('"saved": true', generate.call_args_list[2].args[0])

    def test_cancelled_agent_cannot_write_canvas(self):
        cancel = threading.Event()
        tools = LocalTools(self.chat, cancel)
        cancel.set()
        with self.assertRaises(CancelledError):
            tools.call('create_canvas', {'title':'Не создать', 'content':'text'})
        self.assertEqual(canvases.list_documents(), [])

    def test_retry_of_same_agent_request_does_not_duplicate_canvas(self):
        tools = LocalTools(self.chat, threading.Event(), request_id=41)
        first, _ = tools.call('create_canvas', {'title':'Итог', 'kind':'code', 'content':'print(42)'})
        second, _ = tools.call('create_canvas', {'title':'Итог', 'kind':'code', 'content':'print(42)'})
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(len(canvases.list_documents()), 1)

    def test_agent_cannot_read_other_workspaces_canvas(self):
        doc = canvases.create_document('Другой', chat_id=999, workspace_id='other')
        with self.assertRaises(ValueError):
            LocalTools(self.chat, threading.Event()).call('read_canvas', {'id':doc['id']})

    def test_agent_level_stops_tool_loop_and_preserves_created_document(self):
        generate = Mock(side_effect=[json.dumps({'tool':'create_canvas','arguments':{'title':'Готово','content':'ok'}}),
            *[json.dumps({'tool':'list_library','arguments':{}})]*3])
        with self.assertRaisesRegex(RuntimeError, 'предел действий'):
            run_agent('Продолжай', chat_id=self.chat, history=[], attachments=[], instructions='',
                      level='low', cancelled=threading.Event(), generate=generate)
        self.assertEqual(len(canvases.list_documents()), 1)
        self.assertEqual(generate.call_count, 4)


class ThemeRoundtripTests(unittest.TestCase):
    def test_all_seven_palettes_restore_shared_styles_and_text(self):
        panel = ft.Container(bgcolor=palette.color('#d9ffe6'), border=ft.Border.all(2, ft.Colors.WHITE),
            content=ft.Text('Текст', color=palette.color('#123b43')))
        page = Mock(controls=[panel], overlay=[])
        self.addCleanup(palette.set_theme, page, 'light')
        for theme in palette.THEMES:
            palette.set_theme(page, theme)
            self.assertEqual(panel.bgcolor, palette.THEMES[theme][2].get('#d9ffe6', '#d9ffe6'))
            self.assertEqual(panel.content.color, palette.THEMES[theme][2].get('#123b43', '#123b43'))
            self.assertEqual(panel.border.top.color, ft.Colors.WHITE)
        palette.set_theme(page, 'light')
        self.assertEqual(panel.bgcolor, '#d9ffe6')
        self.assertEqual(panel.content.color, '#123b43')
