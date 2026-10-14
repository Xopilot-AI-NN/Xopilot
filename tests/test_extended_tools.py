"""
Файл: /tests/test_extended_tools.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Реальные проверки файлов Office, изоляции поиска истории и интерактивного Canvas.
          Исполнитель проверок: Codex.
"""
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from App.services import office_documents, chat_search, canvases, workspaces, material_store, agent


class Settings:
    def __init__(self): self.data={}
    def get_setting(self,key): return self.data.get(key)
    def set_setting(self,key,value): self.data[key]=value
    def list_chats(self): return [(1,'Задача Rust',1),(2,'Поездка',2),(-1,'Защищённый Rust',3)]
    def get_messages(self,cid):
        if cid < 0: raise AssertionError('Private history must never be accessed')
        return [SimpleNamespace(id=cid,role='user',content='Сборка Rust проекта' if cid==1 else 'Поездка на море',attachments=[])]


class ExtendedToolsTests(unittest.TestCase):
    def test_agent_returns_real_generated_attachments_and_denies_private_context(self):
        db=Settings()
        with tempfile.TemporaryDirectory() as folder, patch.object(workspaces,'get_db',return_value=db), \
             patch.object(canvases,'get_db',return_value=db), patch.object(material_store,'app_data_dir',return_value=Path(folder)):
            responses=iter([json.dumps({'tool':'create_document','arguments':{'name':'report.docx','content':'Проверка'}}),json.dumps({'final':'Создан документ'})])
            result=agent.run_agent('Создай файл report.docx',chat_id=1,history=[],attachments=[],instructions='',
                level='low',cancelled=threading.Event(),generate=lambda *a,**k:next(responses))
            self.assertEqual(result.files[0][0],'report.docx');self.assertTrue(Path(result.files[0][1]).is_file())
            with self.assertRaises(ValueError):agent.LocalTools(-1,threading.Event())
