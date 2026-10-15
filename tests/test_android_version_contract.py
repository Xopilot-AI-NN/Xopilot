"""
Файл: /tests/test_android_version_contract.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Согласование Python/Dart Flet до начала упаковки Android.
          Исполнитель проверок: Codex.
"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import build_android


class VersionContractTests(unittest.TestCase):
    def test_cli_project_and_plugin_must_match(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'pyproject.toml').write_text('[project]\ndependencies=["flet==1.0.4"]\n')
            plugin=root/'extensions/flet_xopilot_mobile/src/flutter/flet_xopilot_mobile/pubspec.yaml'
            plugin.parent.mkdir(parents=True);plugin.write_text('dependencies:\n  flet: 1.0.4\n')
            (root/'extensions/flet_xopilot_mobile/pyproject.toml').write_text('[project]\ndependencies=["flet==1.0.4"]\n')
            with patch.object(build_android,'ROOT',root),patch('flet.version.flet_version','1.0.4'):
                self.assertEqual(build_android.checked_flet_version(),'1.0.4')
                plugin.write_text('dependencies:\n  flet: 1.0.3\n')
                with self.assertRaisesRegex(RuntimeError,'versions must match'):build_android.checked_flet_version()
                plugin.write_text('dependencies:\n  flet: 1.0.4\n')
                with patch('flet.version.flet_version','1.0.3'):
                    with self.assertRaisesRegex(RuntimeError,'expected 1.0.4'):build_android.checked_flet_version()
