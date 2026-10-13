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
                self.assertEqual(temp.parent, (Path(directory) / "tmp").resolve())
                self.assertEqual(Path.cwd(), (Path(directory) / "runtime").resolve())
                self.assertEqual(Path(os.environ["FLET_APP_STORAGE_CACHE"]).resolve(), (Path(directory) / "cache").resolve())
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
    def test_auto_retries_a_previously_busy_gpu_on_a_later_request(self):
        cpu_engine, gpu_engine = Mock(), Mock()
        capabilities = Mock(__enter__=Mock(return_value=Mock(input_modalities=Mock(audio=False, vision=False))),
                            __exit__=Mock(return_value=False))
        sdk = Mock(Capabilities=Mock(return_value=capabilities), Engine=Mock(side_effect=[cpu_engine, gpu_engine]))
        with tempfile.TemporaryDirectory() as directory, patch.multiple(llm,
                litert_lm=sdk, get_model_path=Mock(return_value=__file__), cache_dir=Mock(return_value=Path(directory)),
                _engine=None, _conversation=None, _loaded_filename=None, _loaded_preference=None,
                _deferred_gpu_retry_at=None, _stateful_history=[], _loaded_modalities=frozenset()), \
                patch.object(acceleration, 'preference', return_value='auto'), \
                patch.object(acceleration, 'candidates', side_effect=[(['cpu'], 'GPU busy'), (['gpu', 'cpu'], '')]) as inspect, \
                patch.object(llm.time, 'monotonic', return_value=100) as clock:
            llm.ensure_model_loaded('model.litertlm')
            llm._stateful_history = [{'role':'user', 'content':[{'type':'text','text':'Keep my context'}]}]
            clock.return_value=110
            llm.ensure_model_loaded('model.litertlm')
            self.assertEqual(inspect.call_count, 1)
            clock.return_value=131
            llm.ensure_model_loaded('model.litertlm')
            self.assertEqual(llm.execution_info()['backend'], 'gpu')
            self.assertEqual(llm._stateful_history[0]['content'][0]['text'], 'Keep my context')
            cpu_engine.close.assert_called_once()
            self.assertEqual(sdk.Engine.call_count, 2)
            self.assertEqual(inspect.call_count, 2)
            llm.unload_model()

    def test_model_button_reports_actual_backend_and_fallback_then_clears_on_unload(self):
        from App.app.buttons import model as model_ui
        with patch.object(model_ui.api_chat, 'is_api_selected', return_value=False), \
                patch.object(model_ui, 'get_selected_chat_model', return_value=llm.DEFAULT_FILENAME), \
                patch.object(model_ui, 'get_loaded_model', return_value=llm.DEFAULT_FILENAME) as loaded, \
                patch.object(model_ui, 'execution_info', return_value={'backend':'cpu', 'reason':'GPU busy'}) as state:
            button, refresh = model_ui.build_model_button()
            label = button.content.controls[1]
            self.assertIn('CPU', label.value)
            self.assertIn('GPU busy', button.tooltip)
            state.return_value={'backend':'gpu', 'reason':''}
            refresh()
            self.assertIn('GPU', label.value)
            self.assertNotIn('GPU busy', button.tooltip)
            loaded.return_value=None
            state.return_value={'backend':None, 'reason':'Idle'}
            refresh()
            self.assertNotIn('GPU', label.value)
            self.assertNotIn('CPU', label.value)

    def test_full_or_sustained_busy_gpu_defers_to_cpu_but_explicit_gpu_is_honored(self):
        with tempfile.NamedTemporaryFile() as model, patch.object(acceleration, "nvidia_devices", return_value=[("RTX", 0, 0)]):
            self.assertEqual(acceleration.candidates(model.name, "auto")[0], ["cpu"])
            self.assertEqual(acceleration.candidates(model.name, "gpu")[0], ["gpu"])
        with tempfile.NamedTemporaryFile() as model, patch.object(acceleration, "time") as timer, \
                patch.object(acceleration, "nvidia_devices", return_value=[("RTX", 6 * 1024**3, 99)]):
            self.assertEqual(acceleration.candidates(model.name, "auto")[0], ["cpu"])
            timer.sleep.assert_called_once_with(1.1)

    def test_container_size_and_moderate_display_activity_do_not_reject_gpu(self):
        with tempfile.NamedTemporaryFile() as model, patch.object(acceleration, "nvidia_devices", return_value=[("RTX", 4 * 1024**3, 35)]), \
                patch.object(acceleration.Path, 'stat', return_value=Mock(st_size=5 * 1024**3)):
            self.assertEqual(acceleration.candidates(model.name, "auto")[0], ["gpu", "cpu"])

    def test_transient_utilization_spike_does_not_force_cpu(self):
        with tempfile.NamedTemporaryFile() as model, patch.object(acceleration, "time"), \
                patch.object(acceleration, "nvidia_devices", side_effect=[[("RTX", 6 * 1024**3, 99)], [("RTX", 6 * 1024**3, 0)]]):
            self.assertEqual(acceleration.candidates(model.name, "auto")[0], ["gpu", "cpu"])

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
                _loaded_preference=None, _loaded_modalities=frozenset(), _execution={"backend": None, "reason": ""}), \
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
