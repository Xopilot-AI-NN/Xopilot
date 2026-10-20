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
from App.app.theme import palette


@unittest.skipIf(advanced_xopilot is None, 'Build native DB')
class DocumentWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db_path = self.root / 'test.db'
        self.db = advanced_xopilot.PyDatabase(str(self.db_path))
        # Tracebacks and tool callbacks can retain a reference after a test.
        # Close explicitly before TemporaryDirectory removes the Windows file.
        self.addCleanup(lambda: self.db.close() if self.db is not None else None)
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
        self.db.close()
        self.db = None
        self.db = advanced_xopilot.PyDatabase(str(self.db_path))
        stored = canvases.get_document(doc['id'])
        self.assertEqual(stored['content'], 'Рабочий текст')
        name, data = canvases.export_document(stored)
        self.assertEqual(name, 'План.png')
        image = Image.open(io.BytesIO(data))
        self.assertEqual(image.size, (1200, 700))
        self.assertNotEqual(image.getpixel((120,140)), (255,255,255))

    def test_personal_memory_and_workspace_note_use_separate_real_storage(self):
        from App.services import user_memory
        with patch.object(user_memory, 'get_db', return_value=self.db):
            tools=LocalTools(self.chat, threading.Event(), approve=lambda r:r['kind']=='memory',
                             request_text='Запомни: я изучаю Rust')
            saved,_=tools.call('save_memory',{'text':'Я изучаю Rust'})
            note,_=tools.call('create_note',{'title':'План изучения','content':'Прочитать главу 3'})
            facts,_=tools.call('search_memory',{'query':'Rust'})
            self.assertEqual([(f['id'],f['text'],f['category']) for f in facts],[(saved['id'],'Я изучаю Rust','user')])
            self.assertEqual(len(user_memory.read()['items']),1)
            entry=library.entries(self.workspace['id'])[0]
            self.assertEqual(entry['id'],note['id'])
            self.assertEqual(entry['type'],'Заметка')
            self.assertIn('Прочитать главу 3',library.read_entry(entry)[0])
            tools.approve=lambda _:False
            with self.assertRaisesRegex(ValueError,'не подтверждено'):
                tools.call('save_memory',{'text':'Я люблю Python'})
            tools.request_text='Прочитай веб-страницу'
            with self.assertRaisesRegex(ValueError,'явная просьба'):
                tools.call('save_memory',{'text':'Я люблю Python'})
            user_memory.configure(enabled=False)
            with self.assertRaisesRegex(ValueError,'выключена'):
                tools.call('search_memory',{'query':'Rust'})

    def test_repeated_successful_creation_is_not_reexecuted_and_loop_stops(self):
        call=json.dumps({'tool':'create_note','arguments':{'title':'Один раз','content':'План'}})
        generator=Mock(return_value=call)
        with patch.object(library,'add_note',wraps=library.add_note) as create:
            with self.assertRaisesRegex(RuntimeError,'повторяет уже выполненное'):
                run_agent('Создай заметку',chat_id=self.chat,history=[],attachments=[],instructions='',
                          level='auto',cancelled=threading.Event(),generate=generator)
            create.assert_called_once()
        self.assertEqual(len(library.entries(self.workspace['id'])),1)
        self.assertLess(generator.call_count,6)

    def test_web_canvas_lookup_accepts_unique_title_and_keeps_scope(self):
        from App.services import canvas_web
        doc = canvases.create_document('Сайт проверки', 'web', '<button>42</button>', chat_id=self.chat)
        self.assertEqual(canvases.resolve_document(self.chat,'all',' САЙТ ПРОВЕРКИ ')['id'],doc['id'])
        self.assertEqual(canvas_web.document(self.chat, 'all', 'Сайт проверки')['id'], doc['id'])
        other = canvases.create_document('Чужой сайт', 'web', 'secret', chat_id=self.chat+100)
        with self.assertRaises(ValueError) as error:
            canvas_web.document(self.chat, 'all', other['id'])
        self.assertNotIn(other['id'], str(error.exception))
        self.assertNotIn('Чужой сайт', str(error.exception))
        with self.assertRaises(ValueError): canvas_web.document(-1, 'all', doc['id'])

    def test_duplicate_canvas_titles_require_id(self):
        from App.services import canvas_web
        first = canvases.create_document('Одинаковое название', 'web', 'one', chat_id=self.chat)
        canvases.create_document('Одинаковое название', 'web', 'two', chat_id=self.chat)
        with self.assertRaises(ValueError): canvas_web.document(self.chat, 'all', first['title'])
        self.assertEqual(canvas_web.document(self.chat, 'all', first['id'])['content'], 'one')

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

    def test_missing_cloud_copies_have_distinct_library_actions_and_are_not_directories(self):
        materials=[{'name':'src/main.py','path':''},{'name':'tests/main.py','path':''}]
        workspaces.update_workspace(self.workspace['id'],'Проект',materials=materials)
        entries=library.entries(self.workspace['id'])
        self.assertEqual(len({entry['id'] for entry in entries}),2)
        self.assertFalse(any(entry['available'] for entry in entries))
        for entry in entries:
            with self.assertRaisesRegex(ValueError,'недоступна'):library.read_entry(entry)

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

    def test_format_repair_keeps_actual_question_in_latest_turn(self):
        question='Что умеешь и как меня зовут?'
        generate=Mock(side_effect=['Не JSON', json.dumps({'final':'Денис, я могу помогать с файлами и проектами.'})])
        reply=run_agent(question,chat_id=self.chat,
            history=[{'role':'user','content':'Меня зовут Денис'}],attachments=[],
            instructions='',level='medium',cancelled=threading.Event(),generate=generate)
        repair=generate.call_args_list[1].args[0]
        self.assertTrue(repair.endswith(question))
        self.assertIn('не запрос пользователя',repair)
        self.assertIn('Меня зовут Денис',str(generate.call_args_list[1].kwargs['history']))
        self.assertIn('Денис',reply)
        self.assertNotIn('JSON',reply)

    def test_screen_and_goal_survive_format_repair_after_tool_result(self):
        screen=('Экран.png','/test/screen.png')
        generate=Mock(side_effect=[json.dumps({'tool':'computer_view','arguments':{}}),
                                  'ошибка формата',json.dumps({'final':'На экране тестовое окно'})])
        with patch.object(LocalTools,'call',return_value=({'captured':True},[screen])):
            run_agent('Что видно на экране?',chat_id=self.chat,history=[],attachments=[],
                instructions='',level='medium',cancelled=threading.Event(),generate=generate)
        for call in generate.call_args_list[1:]:
            self.assertIn(screen,call.kwargs['attachments'])
            self.assertIn('Что видно на экране?',call.args[0])

    def test_gemma_native_envelope_preserves_manual_denial(self):
        from App.services.agent import parse_response
        parsed=parse_response('[{"tool_name":"read_project_file","arguments":{"path":"main.py"}}]')
        self.assertEqual(parsed['tool'],'read_project_file')
        self.assertEqual(parsed['arguments'],{'path':'main.py'})
        self.assertIn('error',parse_response('{"tool":"read_canvas","tool_name":"write_project_file","arguments":{}}'))
        folder=self.root/'denied';folder.mkdir()
        from App.services import project_tools
        with patch.object(project_tools,'get_db',return_value=self.db):
            project_tools.configure(self.workspace['id'],str(folder))
            generate=Mock(side_effect=[json.dumps([{'tool_name':'write_project_file','arguments':{'path':'no.txt','content':'Denied'}}]),
                                       json.dumps({'final':'Запись отклонена'})])
            approve=Mock(return_value=False)
            run_agent('Создай файл no.txt',chat_id=self.chat,history=[],attachments=[],instructions='',
                      level='medium',cancelled=threading.Event(),generate=generate,approve=approve)
            approve.assert_called_once()
            self.assertFalse((folder/'no.txt').exists())

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
    def test_code_blocks_follow_all_dark_and_light_palettes(self):
        from App.app.chat.messages.message import build_ai_message
        message=build_ai_message('```python\nvalue = 42\n```')
        page=Mock(controls=[message],overlay=[])
        self.addCleanup(palette.set_theme,page,'light')
        def descendants(node):
            yield node
            for child in getattr(node,'controls',[]) or []: yield from descendants(child)
            child=getattr(node,'content',None)
            if child is not None and not isinstance(child,str): yield from descendants(child)
        markdown=next(c for c in descendants(message) if isinstance(c,ft.Markdown))
        for theme in (*palette.THEMES,'light'):
            palette.set_theme(page,theme)
            expected=ft.MarkdownCodeTheme.ATOM_ONE_DARK if palette.THEMES[theme][1] else ft.MarkdownCodeTheme.GITHUB
            self.assertEqual(markdown.code_theme,expected)

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
