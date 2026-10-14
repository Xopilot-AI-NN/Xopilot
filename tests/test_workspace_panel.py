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
            self.assertTrue(any(isinstance(c,ft.Dropdown) and c.label=='Подтверждение действий' for c in controls))
            names[0].value='Updated site'
            workspaces.update_workspace(identifier,'Site',materials=[{'name':'new.txt','path':''}])
            panel.actions[-1].on_click(None)
            item=next(w for w in workspaces.list_workspaces() if w['id']==identifier)
            self.assertEqual(item['name'],'Updated site');self.assertEqual(item['materials'][0]['name'],'new.txt')
            self.assertEqual(project_tools.approval_mode(identifier),'manual')

    def test_automatic_mode_requires_explicit_choice_in_confirmation(self):
        db=Settings();page=Mock(width=1000,height=800,web=True)
        with patch.object(workspaces,'get_db',return_value=db),patch.object(project_tools,'get_db',return_value=db):
            identifier=workspaces.create_workspace('Trusted')['id']
            panel=build_workspace_settings(page,identifier)
            mode=next(c for c in descendants(panel) if isinstance(c,ft.Dropdown) and c.label=='Подтверждение действий')
            mode.value='automatic';mode.on_change(Mock(control=mode))
            self.assertEqual(project_tools.approval_mode(identifier),'manual')
            page.show_dialog.call_args.args[0].actions[-1].on_click(None)
            self.assertEqual(project_tools.approval_mode(identifier),'automatic')
            mode.value='manual';mode.on_change(Mock(control=mode))
            self.assertEqual(project_tools.approval_mode(identifier),'manual')
