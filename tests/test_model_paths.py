"""
Файл: tests/test_model_paths.py
Разработчик: DenBroLiik
Описание: Пользовательские каталоги моделей, совместимость и путь нативной БД.
"""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from App.services import db, llm, paths


class ModelPathTests(unittest.TestCase):
    def test_user_models_override_legacy_and_list_both(self):
        with tempfile.TemporaryDirectory() as directory:
            user, legacy = Path(directory) / "user", Path(directory) / "legacy"
            user.mkdir()
            legacy.mkdir()
            (user / "same.litertlm").touch()
            (legacy / "same.litertlm").touch()
            (legacy / "old.litertlm").touch()
            with patch.multiple(llm, MODELS_DIR=str(user), LEGACY_MODELS_DIR=legacy):
                self.assertEqual(llm.list_local_models(), ["old.litertlm", "same.litertlm"])
                self.assertEqual(llm.get_model_path("same.litertlm"), str(user / "same.litertlm"))
                self.assertEqual(llm.get_model_path("old.litertlm"), str(legacy / "old.litertlm"))
                with self.assertRaises(ValueError):
                    llm.get_model_path("../outside.litertlm")

    def test_windows_and_linux_data_directories(self):
        with patch.dict(os.environ, {"APPDATA": "/windows", "XDG_DATA_HOME": "/linux"}):
            with patch.object(paths.platform, "system", return_value="Windows"):
                self.assertEqual(paths.app_data_dir(), Path("/windows/Xopilot"))
            with patch.object(paths.platform, "system", return_value="Linux"):
                self.assertEqual(paths.app_data_dir(), Path("/linux/Xopilot"))

    def test_python_database_wrapper_uses_user_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            native = type("Native", (), {"PyDatabase": staticmethod(lambda path: path)})
            with patch.object(paths, "app_data_dir", return_value=Path(directory)), patch.multiple(
                db, advanced_xopilot=native, _db=None,
            ):
                self.assertEqual(db.get_db(), str(Path(directory) / "xopilot.db"))
