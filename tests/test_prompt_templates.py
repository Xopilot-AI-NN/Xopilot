"""
Файл: /tests/test_prompt_templates.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Проверяю хранение шаблонов, подтверждение удаления и вставку без отправки.
          Исполнитель: Codex. Личная переписка не используется.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from App.services import db,prompt_templates as store,message_navigation


@unittest.skipIf(db.advanced_xopilot is None,'Native DB required')
class TemplateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'qa.db';self.native=db.advanced_xopilot.PyDatabase(str(self.path),key='ea'*32)
        self.addCleanup(lambda:self.native.close());p=patch.object(db,'_db',self.native);p.start();self.addCleanup(p.stop)

    def test_template_survives_reopen_edits_and_deletion_without_recreating_stale_id(self):
        identifier=store.save('Проверка кода','QA_TEMPLATE_PRIVATE_379\n  сохранить отступ')
        self.native.close();self.native=db.advanced_xopilot.PyDatabase(str(self.path),key='ea'*32)
        with patch.object(db,'_db',self.native):
            self.assertEqual(store.list_templates('пРОВЕРКА')[0]['id'],identifier)
            store.save('Обновлённый','Другой запрос',identifier)
            self.assertEqual(store.list_templates()[0]['body'],'Другой запрос')
            self.assertTrue(store.delete(identifier));self.assertFalse(store.delete(identifier))
            with self.assertRaises(ValueError):store.save('Не воскресить','text',identifier)
        self.assertNotIn(b'QA_TEMPLATE_PRIVATE_379',self.path.read_bytes())

    def test_insertion_preserves_draft_and_indentation_and_rejects_empty_template(self):
        self.assertEqual(store.insert('Мой черновик','  код\n'), 'Мой черновик\n\n  код\n')
        self.assertEqual(store.insert('','инструкция'),'инструкция')
        for title,body in [('', 'text'),('Имя','   '),('a'*81,'text')]:
            with self.assertRaises(ValueError):store.save(title,body)

    async def test_manager_apply_editor_and_confirmed_delete_use_real_storage(self):
        from App.app.chat.composer.prompt_templates import open_templates
        class Page:
            height=800
            def __init__(self):self.dialogs=[]
            def show_dialog(self,value):self.dialogs.append(value)
            def pop_dialog(self):self.dialogs.pop()
            def update(self):pass
        page=Page();applied=[]
        async def apply(body):applied.append(body)
        store.save('Код','Проверь ошибки')
        open_templates(page,apply)
        manager=page.dialogs[-1];row=manager.content.controls[-1].controls[0]
        await row.content.controls[-1].controls[0].on_click(None)
        self.assertEqual(applied,['Проверь ошибки']);self.assertEqual(page.dialogs,[])
        open_templates(page,apply);manager=page.dialogs[-1]
        manager.content.controls[2].on_click(None)
        editor=page.dialogs[-1];editor.content.controls[0].value='План';editor.content.controls[1].value='Составь план'
        editor.actions[-1].on_click(None)
        self.assertEqual(len(store.list_templates()),2)
        row=manager.content.controls[-1].controls[0]
        row.content.controls[-1].controls[2].on_click(None)
        self.assertEqual(len(store.list_templates()),2)
        page.dialogs[-1].actions[-1].on_click(None)
        self.assertEqual(len(store.list_templates()),1)

    def test_message_search_filters_author_and_bookmarks(self):
        cid=self.native.create_chat('QA')
        user=self.native.add_message(cid,'user','Atlas вопрос');ai=self.native.add_message(cid,'ai','Atlas ответ')
        self.assertEqual([m['message_id'] for m in message_navigation.search(cid,'Atlas',role='ai')['items']],[ai])
        message_navigation.toggle(cid,user)
        self.assertEqual(message_navigation.search(cid,bookmarks=True,role='ai')['total'],0)
        self.assertEqual(message_navigation.search(cid,bookmarks=True,role='user')['total'],1)
        with self.assertRaises(ValueError):message_navigation.search(cid,'Atlas',role='system')


class PackagedTemplateTests(unittest.TestCase):
    def test_apply_in_packaged_app_preserves_composer_without_sending(self):
        import subprocess,sys
        script=r'''
import sys,tempfile,asyncio
from pathlib import Path
from unittest.mock import Mock,patch,AsyncMock
import flet as ft
sys.path.insert(0,str(Path.cwd()/'App'))
from app import main
from services import db,chat_store,prompt_templates
page=Mock(width=393,height=851,web=True,services=[],_dialogs=Mock(controls=[]))
def walk(c):
 yield c
 for name in ('controls','content','items'):
  v=getattr(c,name,None)
  for child in v if isinstance(v,list) else [v]:
   if isinstance(child,ft.BaseControl):yield from walk(child)
with tempfile.TemporaryDirectory() as folder,db.advanced_xopilot.PyDatabase(str(Path(folder)/'qa.db'),key='be'*32) as native:
 with patch.object(db,'_db',native),patch.object(main,'install_theme'),patch.object(main,'get_selected_chat_model',return_value=None),patch.object(ft.ListView,'update'),patch.object(ft.TextField,'update'),patch.object(ft.TextField,'focus',new=AsyncMock()):
  cid=native.create_chat('Template QA');native.add_message(cid,'user','Существующее сообщение')
  prompt_templates.save('Проверка','Проверь код и предложи улучшения')
  with patch.object(chat_store,'_active_chat_id',cid):
   ui=main.build_app_ui(page)
   composer=next(c for c in walk(ui) if isinstance(c,ft.TextField) and c.hint_text=='Напишите сообщение…')
   composer.value='Мой черновик'
   entry=next(c for c in walk(ui) if isinstance(c,ft.PopupMenuItem) and getattr(c.content,'value',None)=='Шаблоны запросов')
   entry.on_click(None);dialog=page.show_dialog.call_args.args[0]
   row=dialog.content.controls[-1].controls[0]
   asyncio.run(row.content.controls[-1].controls[0].on_click(None))
   assert composer.value=='Мой черновик\n\nПроверь код и предложи улучшения'
   assert len(native.get_messages(cid))==1
print('Packaged templates preserve draft; no message sent.')
'''
        result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
