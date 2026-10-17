"""
Файл: /tests/test_account_deletion.py
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: Проверка отложенного стирания в отдельном каталоге. Исполнитель: Codex.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from App.services import account_deletion as deletion


class ErasureTests(unittest.TestCase):
    def test_restart_erases_only_private_directory_and_does_not_follow_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'Xopilot';root.mkdir()
            source=Path(tmp)/'original.txt';source.write_text('keep')
            (root/'materials').mkdir();(root/'materials'/'copy').write_text('delete')
            (root/'external').symlink_to(source)
            with patch.object(deletion,'app_data_dir',return_value=root):
                self.assertFalse(deletion.perform_pending_erasure())
                deletion.schedule_local_erasure()
                self.assertTrue(deletion.perform_pending_erasure())
                self.assertEqual(list(root.iterdir()),[])
            self.assertEqual(source.read_text(),'keep')

    def test_wipe_failure_keeps_marker_for_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'Xopilot';root.mkdir();(root/'materials').mkdir()
            with patch.object(deletion,'app_data_dir',return_value=root):
                deletion.schedule_local_erasure()
                with patch.object(deletion.shutil,'rmtree',side_effect=OSError('locked')):
                    with self.assertRaises(OSError):deletion.perform_pending_erasure()
                self.assertTrue((root/deletion.MARKER).exists())

    def test_cloud_failure_never_schedules_local_erasure(self):
        with patch('App.services.cloud_account.state',return_value={'email':'qa@example.invalid','account_id':'a'}),\
             patch('App.services.cloud_account.request',side_effect=OSError('offline')),\
             patch.object(deletion,'schedule_local_erasure') as erase:
            with self.assertRaises(OSError):deletion.delete_account('qa@example.invalid')
            erase.assert_not_called()
