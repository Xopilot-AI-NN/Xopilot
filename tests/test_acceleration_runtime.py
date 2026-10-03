"""Device fallback and source-watch isolation, without loading a real model."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from App.services import acceleration, runtime, llm
from App.services import material_store
from App.app.file_selection import pick_materials
from unittest.mock import AsyncMock
import flet as ft


class RuntimeTests(unittest.TestCase):
    def test_cli_temp_and_working_directory_move_out_of_watched_sources(self):
        previous_cwd, previous_temp = Path.cwd(), tempfile.tempdir
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ), \
                patch.object(runtime, "app_data_dir", return_value=Path(directory)):
            try:
                os.environ["TMPDIR"] = "/watched/App/.flet/storage/temp"
                runtime.configure_runtime()
                temp = Path(tempfile.mkdtemp())
                self.assertEqual(temp.parent, Path(directory) / "tmp")
                self.assertEqual(Path.cwd(), Path(directory) / "runtime")
                self.assertEqual(os.environ["FLET_APP_STORAGE_CACHE"], str(Path(directory) / "cache"))
            finally:
                os.chdir(previous_cwd)
                tempfile.tempdir = previous_temp


class FileSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_path_and_browser_bytes_produce_independent_copies(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(material_store, "app_data_dir", return_value=Path(directory)):
            original = Path(directory) / "original.txt"
            original.write_text("Содержимое")
            for web in (False, True):
                file = ft.FilePickerFile(name="brief.txt", size=8, id=1,
                    path=None if web else str(original), bytes=b"browser" if web else None)
                picker = Mock(pick_files=AsyncMock(return_value=[file]))
                files = await pick_materials(Mock(web=web), picker)
                self.assertEqual(len(files), 1)
                path = Path(files[0].path)
                self.assertNotEqual(path, original)
                self.assertEqual(path.read_bytes(), b"browser" if web else original.read_bytes())
                self.assertEqual(picker.pick_files.call_args.kwargs["with_data"], web)
            original.unlink()
            self.assertTrue(path.exists())

    async def test_cancel_returns_no_files_and_does_not_write_materials(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(material_store, "app_data_dir", return_value=Path(directory)):
            picker = Mock(pick_files=AsyncMock(return_value=[]))
            self.assertEqual(await pick_materials(Mock(web=False), picker), [])
            self.assertEqual(list(Path(directory).iterdir()), [])


class AccelerationTests(unittest.TestCase):
    def test_busy_or_full_gpu_uses_cpu_in_auto_but_explicit_gpu_is_honored(self):
        with tempfile.NamedTemporaryFile() as model, patch.object(acceleration, "nvidia_devices", return_value=[("RTX", 512 * 1024**2, 0)]):
            self.assertEqual(acceleration.candidates(model.name, "auto")[0], ["cpu"])
            self.assertEqual(acceleration.candidates(model.name, "gpu")[0], ["gpu"])
        with tempfile.NamedTemporaryFile() as model, patch.object(acceleration, "nvidia_devices", return_value=[("RTX", 6 * 1024**3, 99)]):
            self.assertEqual(acceleration.candidates(model.name, "auto")[0], ["cpu"])

    def test_gpu_init_failure_falls_back_only_in_auto(self):
        capabilities = Mock()
        capabilities.__enter__ = Mock(return_value=Mock(input_modalities=Mock(audio=False, vision=False)))
        capabilities.__exit__ = Mock(return_value=False)
        cpu_engine = Mock()
        sdk = Mock(Capabilities=Mock(return_value=capabilities))
        sdk.Engine.side_effect = [RuntimeError("driver unavailable"), cpu_engine]
        with tempfile.TemporaryDirectory() as directory, patch.multiple(llm,
                litert_lm=sdk, get_model_path=Mock(return_value=__file__),
                cache_dir=Mock(return_value=Path(directory)),
                _engine=None, _conversation=None, _loaded_filename=None,
                _loaded_preference=None, _execution={"backend": None, "reason": ""}), \
                patch.object(acceleration, "preference", return_value="auto"), \
                patch.object(acceleration, "candidates", return_value=(["gpu", "cpu"], "")):
            llm.load_model("model.litertlm")
            self.assertEqual(llm.execution_info()["backend"], "cpu")
            self.assertIn("driver unavailable", llm.execution_info()["reason"])
            self.assertEqual(sdk.Engine.call_count, 2)
            llm.unload_model()
            sdk.Engine.side_effect = RuntimeError("driver unavailable")
            with patch.object(acceleration, "candidates", return_value=(["gpu"], "")):
                with self.assertRaisesRegex(RuntimeError, "GPU"):
                    llm.load_model("model.litertlm")
            self.assertFalse(llm.is_model_loaded())

    def test_device_preference_change_reloads_before_next_request(self):
        loader = Mock()
        with patch.multiple(llm, _engine=Mock(), _conversation=Mock(),
                _loaded_filename="model.litertlm", _loaded_preference="cpu", _load_model=loader), \
                patch.object(acceleration, "preference", return_value="gpu"):
            llm.ensure_model_loaded("model.litertlm")
            loader.assert_called_once()
