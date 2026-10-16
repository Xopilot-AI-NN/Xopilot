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


class AndroidIdentityTests(unittest.TestCase):
    def test_default_and_explicit_legacy_update_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'pyproject.toml').write_text(
                '[tool.flet]\norg="by.xopilot"\n[tool.flet.android]\nbundle_id="by.xopilot.app"\n')
            with patch.object(build_android,'ROOT',root):
                self.assertEqual(build_android.android_bundle_id(),'by.xopilot.app')
                self.assertEqual(build_android.android_bundle_id(org='ru.xopilot'),'ru.xopilot.xopilot')
                self.assertEqual(build_android.android_bundle_id(org='ru.xopilot',bundle_id='by.xopilot.test'),'by.xopilot.test')

    def test_final_manifest_must_have_expected_identity(self):
        from scripts.verify_android_apk import verify_package
        verify_package("package: name='by.xopilot.app' versionCode='6105'",'by.xopilot.app')
        with self.assertRaisesRegex(RuntimeError,'Unexpected Android package'):
            verify_package("package: name='ru.xopilot.xopilot' versionCode='6105'",'by.xopilot.app')
        with self.assertRaises(RuntimeError):verify_package('', 'by.xopilot.app')
