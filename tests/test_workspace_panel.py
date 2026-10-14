"""
Файл: /tests/test_workspace_panel.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Единая панель пространства и сохранение актуальной библиотеки.
          Исполнитель проверок: Codex.
"""
import unittest
from unittest.mock import Mock,patch
import flet as ft
from App.services import workspaces,project_tools
from App.app.workspace_browser import build_workspace_settings
from App.app.library_browser import build_library_dialog


class Settings:
    def __init__(self):self.data={}
    def get_setting(self,key):return self.data.get(key)
    def set_setting(self,key,value):self.data[key]=value


def descendants(node):
    yield node
    for key in ('content','controls','actions','title'):
        value=getattr(node,key,None)
        if isinstance(value,ft.Control):yield from descendants(value)
        elif isinstance(value,list):
            for child in value:
                if isinstance(child,ft.Control):yield from descendants(child)


class PanelTests(unittest.TestCase):
    def test_library_opens_same_panel_and_settings_save_preserves_new_materials(self):
        db=Settings();page=Mock(width=393,height=851,web=True)
        with patch.object(workspaces,'get_db',return_value=db),patch.object(project_tools,'get_db',return_value=db):
            identifier=workspaces.create_workspace('Site')['id']
            panel=build_library_dialog(page,identifier)
            controls=list(descendants(panel))
            names=[c for c in controls if isinstance(c,ft.TextField) and c.label=='Название']
            self.assertEqual(len(names),1)
            self.assertTrue(any(isinstance(c,ft.TextField) and c.hint_text=='Поиск в библиотеке' for c in controls))
            self.assertFalse(any(isinstance(c,ft.Dropdown) and c.label=='Подтверждение действий' for c in controls))
            names[0].value='Updated site'
            workspaces.update_workspace(identifier,'Site',materials=[{'name':'new.txt','path':''}])
            panel.actions[-1].on_click(None)
            item=next(w for w in workspaces.list_workspaces() if w['id']==identifier)
            self.assertEqual(item['name'],'Updated site');self.assertEqual(item['materials'][0]['name'],'new.txt')
            self.assertEqual(project_tools.approval_mode(identifier),'manual')

    def test_chat_confirmation_button_is_explicit_and_scoped_to_current_chat(self):
        from App.app.confirmation_button import build_confirmation_button
        db=Settings();page=Mock(width=1000,height=800,web=True);current=[1]
        with patch.object(project_tools,'get_db',return_value=db):
            button,refresh=build_confirmation_button(page,lambda:current[0])
            button.on_click(None)
            self.assertEqual(project_tools.chat_approval_mode(1),'manual')
            page.show_dialog.call_args.args[0].actions[-1].on_click(None)
            self.assertEqual(project_tools.chat_approval_mode(1),'automatic')
            self.assertEqual(button.content.controls[0].icon,ft.Icons.AUTO_MODE)
            current[0]=2;refresh()
            self.assertEqual(button.content.controls[1].value,'Вручную')
            self.assertEqual(button.content.controls[0].icon,ft.Icons.FACT_CHECK_OUTLINED)
            self.assertEqual(project_tools.chat_approval_mode(2),'manual')
            current[0]=1;refresh();button.on_click(None)
            self.assertEqual(project_tools.chat_approval_mode(1),'manual')
            count=page.show_dialog.call_count
            button.on_click(None)
            self.assertEqual(project_tools.chat_approval_mode(1),'automatic')
            self.assertEqual(button.content.controls[0].icon,ft.Icons.AUTO_MODE)
            self.assertEqual(page.show_dialog.call_count,count)
            current[0]=-1;refresh();self.assertFalse(button.visible)

    def test_empty_folder_can_be_connected_as_project_and_copied_without_error(self):
        import tempfile
        import asyncio
        from App.services import library
        from App.app.library_browser import build_library_content
        db=Settings();page=Mock(width=1000,height=800,web=True)
        with tempfile.TemporaryDirectory() as folder,patch.object(workspaces,'get_db',return_value=db),patch.object(project_tools,'get_db',return_value=db):
            identifier=workspaces.create_workspace('Empty project')['id']
            content=build_library_content(page,identifier)
            folders=next(c for c in descendants(content) if isinstance(c,ft.OutlinedButton) and c.content=='Папка')
            folders.on_click(None);dialog=page.show_dialog.call_args.args[0]
            field=next(c for c in descendants(dialog) if isinstance(c,ft.TextField) and c.label=='Папка на этом компьютере')
            field.value=folder
            asyncio.run(dialog.actions[-1].on_click(None))
            self.assertEqual(project_tools.settings(identifier)['root'],folder)
            self.assertEqual(project_tools.list_files(identifier),[])
            self.assertEqual(library.import_folder(folder),([],[]))
