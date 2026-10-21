"""
Файл: /tests/test_message_navigation.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Проверяю поиск, постоянные локальные закладки и переход к результату в интерфейсе.
          Исполнитель: Codex. Используется отдельная зашифрованная БД.
"""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from App.services import db,message_navigation as nav


@unittest.skipIf(db.advanced_xopilot is None,'Native DB required')
class NavigationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'qa.db'
        self.native=db.advanced_xopilot.PyDatabase(str(self.path),key='ad'*32);self.addCleanup(lambda:self.native.close())
        p=patch.object(db,'_db',self.native);p.start();self.addCleanup(p.stop)
        self.cid=self.native.create_chat('QA');self.other=self.native.create_chat('Other')
        self.ids=[]
        for i in range(75):self.ids.append(self.native.add_message(self.cid,'user','Ответ '+str(i)+' про Atlas'))
        self.secret=self.native.add_message(self.other,'user','Atlas из другого чата')

    def test_search_all_history_is_case_insensitive_paginated_and_scoped(self):
        first=nav.search(self.cid,'ATLAS',limit=30)
        self.assertEqual(first['total'],75);self.assertTrue(first['has_more'])
        second=nav.search(self.cid,'atlas',offset=first['next_offset'],limit=30)
        self.assertFalse({m['message_id'] for m in first['items']} & {m['message_id'] for m in second['items']})
        self.assertEqual(nav.search(self.cid,'Ответ 0')['items'][0]['message_id'],self.ids[0])
        self.assertEqual(nav.search(self.cid,'другого')['total'],0)
        self.assertEqual(nav.search(self.cid)['total'],0)
        for cid in (-1,0,99999):
            with self.assertRaises(ValueError):nav.search(cid,'Atlas')

    def test_bookmarks_persist_without_text_copy_and_deleted_messages_disappear(self):
        mid=self.ids[0]
        self.assertTrue(nav.toggle(self.cid,mid))
        self.assertNotIn('Atlas',self.native.get_setting(nav.KEY))
        self.native.close();self.native=db.advanced_xopilot.PyDatabase(str(self.path),key='ad'*32)
        with patch.object(db,'_db',self.native):
            self.assertTrue(nav.marked(mid))
            self.assertEqual(nav.search(self.cid,bookmarks=True)['total'],1)
            self.assertEqual(nav.search(self.other,bookmarks=True)['total'],0)
            self.assertFalse(nav.toggle(self.cid,mid));self.assertEqual(nav.search(self.cid,bookmarks=True)['total'],0)
            nav.toggle(self.cid,mid);self.native.delete_message(mid)
            self.assertEqual(nav.search(self.cid,bookmarks=True)['total'],0)
            with self.assertRaises(ValueError):nav.toggle(self.cid,self.secret)

    async def test_result_opens_original_message_and_late_load_after_close_is_ignored(self):
        from App.app.chat.messages.message_navigation import open_navigation
        class Page:
            height=740
            def update(self):pass
            def show_dialog(self,value):self.dialog=value
            def pop_dialog(self):self.dialog=None
            def run_task(self,call):self.load=call
        page=Page();jumps=[]
        async def jump(cid,mid):jumps.append((cid,mid))
        nav.toggle(self.cid,self.ids[0]);open_navigation(page,self.cid,jump,bookmarks=True)
        self.assertFalse(page.dialog.content.controls[0].autofocus)
        await page.load()
        author=page.dialog.content.controls[1];author.value='ai';await author.on_select(None)
        self.assertEqual(page.dialog.content.controls[-2].controls,[])
        author.value='user';await author.on_select(None)
        rows=page.dialog.content.controls[-2]
        await rows.controls[0].on_click(None)
        self.assertEqual(jumps,[(self.cid,self.ids[0])]);self.assertIsNone(page.dialog)
        await page.load();self.assertIsNone(page.dialog)


class PackagedNavigationTests(unittest.TestCase):
    def test_search_result_scrolls_to_old_message_with_bounded_render_window(self):
        import subprocess,sys
        script=r'''
import sys,tempfile,asyncio
from pathlib import Path
from unittest.mock import Mock,patch
import flet as ft
sys.path.insert(0,str(Path.cwd()/'App'))
from app import main
from services import db,chat_store
page=Mock(width=393,height=851,web=True,services=[],_dialogs=Mock(controls=[]))
scrolled=[]
async def scroll(self,**kwargs):scrolled.append((self,kwargs))
def walk(c):
 yield c
 for name in ('controls','content','items'):
  v=getattr(c,name,None)
  for child in v if isinstance(v,list) else [v]:
   if isinstance(child,ft.BaseControl):yield from walk(child)
with tempfile.TemporaryDirectory() as folder,db.advanced_xopilot.PyDatabase(str(Path(folder)/'qa.db'),key='be'*32) as native:
 with patch.object(db,'_db',native),patch.object(main,'install_theme'),patch.object(main,'get_selected_chat_model',return_value=None),patch.object(ft.ListView,'update'),patch.object(ft.TextField,'update'),patch.object(ft.ListView,'scroll_to',new=scroll):
  cid=native.create_chat('Navigation QA');first=native.add_message(cid,'user','UNIQUE_OLD_RESULT')
  for i in range(80):native.add_message(cid,'ai','Later '+str(i))
  with patch.object(chat_store,'_active_chat_id',cid):
   ui=main.build_app_ui(page)
   entry=next(c for c in walk(ui) if isinstance(c,ft.PopupMenuItem) and getattr(c.content,'value',None)=='Поиск в чате')
   asyncio.run(page.on_keyboard_event(ft.KeyboardEvent(name='keyboard_event',control=page,key='f',ctrl=True,shift=False,alt=False,meta=False)))
   dialog=page.show_dialog.call_args.args[0]
   dialog.content.controls[0].value='UNIQUE_OLD_RESULT'
   asyncio.run(page.run_task.call_args.args[0]())
   rows=dialog.content.controls[-2]
   asyncio.run(rows.controls[0].on_click(None))
   assert scrolled[-1][1]['scroll_key']=='message-'+str(first)
   assert len(scrolled[-1][0].controls)<=30
   assert scrolled[-1][0].build_controls_on_demand is False
   latest=next(c for c in walk(ui) if isinstance(c,ft.PopupMenuItem) and getattr(c.content,'value',None)=='К последним сообщениям')
   latest.on_click(None)
   assert scrolled[-1][0].build_controls_on_demand is True
   assert any(getattr(c,'data',None)!=first for c in scrolled[-1][0].controls)
print('Packaged search and scroll: OK')
'''
        result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
