"""
Файл: /tests/test_computer_chat_session.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Проверяю границы разрешения экрана и сохранение кадров. Исполнитель: Codex.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from PIL import Image
from App.services import desktop_control as desktop


class ChatSessionTests(unittest.TestCase):
    def tearDown(self):desktop.close_chat_session()

    def test_same_chat_reuses_permission_and_switch_closes_previous(self):
        with patch.object(desktop,'ComputerSession') as factory:
            first,second=Mock(),Mock();factory.side_effect=[first,second]
            self.assertIs(desktop.chat_session(1),first)
            self.assertIs(desktop.chat_session(1),first)
            first.close.assert_not_called()
            self.assertIs(desktop.chat_session(2),second)
            first.close.assert_called_once()
            desktop.close_chat_session();second.close.assert_called_once()

    def test_preview_survives_original_and_does_not_contain_raw_screen_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.png';target=Path(folder)/'stored.jpg'
            Image.new('RGB',(1920,1200),'blue').save(source)
            def store(name,*,data):target.write_bytes(data);return str(target)
            with patch('App.services.material_store.store_material',side_effect=store):
                files=desktop.preview_files([('screen.png',str(source))])
            source.unlink()
            self.assertEqual(files,[('Экран компьютера.jpg',str(target))])
            with Image.open(target) as image:self.assertEqual(image.size,(960,600))

    def test_two_starts_in_one_chat_request_permission_only_once(self):
        import threading
        bridge=Mock();bridge.process.poll.return_value=None
        bridge.call.return_value={'size':[1920,1200]}
        approve=Mock(return_value=True)
        session=desktop.ComputerSession(chat_scoped=True)
        with patch.object(desktop,'Bridge',return_value=bridge):
            first=session.start(threading.Event(),approve)
            second=session.start(threading.Event(),approve)
        try:
            self.assertEqual(first['scope'],'chat')
            self.assertEqual(first,second)
            approve.assert_called_once()
            bridge.call.assert_called_once_with('start',cancelled=unittest.mock.ANY)
        finally:session.close()
