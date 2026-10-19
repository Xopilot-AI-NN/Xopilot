"""
Файл: /tests/test_packaged_chat_navigation.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Проверяю чаты в реальной схеме импорта APK app/services, без префикса App.
          Исполнитель: Codex. Данные изолированы во временной зашифрованной БД.
"""
from pathlib import Path
import subprocess
import sys
import unittest


class PackagedChatTests(unittest.TestCase):
    def test_create_delete_and_already_deleted_chat_in_packaged_layout(self):
        script=r'''
import sys,tempfile,asyncio
from pathlib import Path
from unittest.mock import Mock,patch
import flet as ft
sys.path.insert(0,str(Path.cwd()/'App'))
from app import main as main_ui
from services import db,chat_store
from app.tasks.task_messages import TaskMessages
page=Mock(width=393,height=851,web=True,services=[],_dialogs=Mock(controls=[]))
with tempfile.TemporaryDirectory() as folder, db.advanced_xopilot.PyDatabase(str(Path(folder)/'qa.db'),key='ba'*32) as native:
    with patch.object(db,'_db',native),patch.object(chat_store,'_active_chat_id',None),patch.object(main_ui,'install_theme'),patch.object(main_ui,'get_selected_chat_model',return_value=None),patch.object(ft.TextField,'update'),patch.object(ft.ListView,'update'):
        original=chat_store.create_new_chat()
        native.add_message(original,'user','Isolated fixture to preserve')
        ui=main_ui.build_app_ui(page)
        header=ui.content.content.controls[0].controls[-1].content.controls[0]
        menu=header.content.controls[-1]
        menu.items[0].on_click(None)
        empty=chat_store.get_or_create_active_chat_id()
        assert empty!=original
        assert header.content.controls[1].controls[0].value=='Новый чат'
        menu.items[0].on_click(None)
        assert chat_store.get_or_create_active_chat_id()==empty
        delete=next(item for item in menu.items if getattr(item.content,'value',None)=='Удалить чат')
        delete.on_click(None)
        page.show_dialog.call_args.args[0].actions[-1].on_click(None)
        current=chat_store.get_or_create_active_chat_id()
        assert current not in (original,empty)
        assert native.get_messages(current)==[]
        assert any(row[0]==original for row in native.list_chats())
        # Remote deletion or a previous successful delete followed by failed UI navigation.
        native.delete_chat(current)
        page.show_dialog.reset_mock()
        delete.on_click(None)
        page.show_dialog.call_args.args[0].actions[-1].on_click(None)
        restored=chat_store.get_or_create_active_chat_id()
        assert restored!=current
        assert native.get_messages(restored)==[]
        assert any(row[0]==original for row in native.list_chats())
        assert not any(isinstance(call.args[0],ft.SnackBar) for call in page.show_dialog.call_args_list)
        journal=TaskMessages(page,restored,None,current_chat=lambda:restored,chat_list=Mock(controls=[]),save=Mock(),update=Mock())
        item=journal.make_item(dict(id='start',tool='computer_start',label='Доступ к компьютеру',arguments={},phase='result',result={'active':True}))
        revoke=item['card'].content.controls[0].controls[1]
        with patch('app.tasks.task_messages.close_chat_session') as close,patch.object(ft.TextButton,'update'):
            asyncio.run(revoke.on_click(None))
            close.assert_called_once()
        asyncio.run(page.on_disconnect(None))
print('Packaged chat navigation and revoke: OK')
'''
        result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
