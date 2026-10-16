"""Keep optional encoders out of text chat and preserve transitions to media."""
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from unittest.mock import AsyncMock
import gc
import weakref
from types import SimpleNamespace

from App.services import llm, model_settings
from App.services.lazy_imports import OptionalModule
from App.services.runtime import IdleMemoryCleanup


class LazyMediaTests(unittest.TestCase):
    def test_app_import_does_not_import_media_or_load_native_model_library(self):
        result = subprocess.run([sys.executable, "-c", """
import sys
from App.app import main
assert not {'cv2', 'numpy', 'onnxruntime', 'docx', 'pypdf'} & sys.modules.keys()
"""], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_optional_library_is_loaded_once_and_missing_dependency_stays_optional(self):
        module = OptionalModule('example')
        actual = Mock(value=123)
        with patch('App.services.lazy_imports.importlib.import_module', return_value=actual) as loader:
            loader.assert_not_called()
            self.assertTrue(module)
            self.assertEqual(module.value, 123)
            loader.assert_called_once_with('example')
        missing = OptionalModule('absent')
        with patch('App.services.lazy_imports.importlib.import_module', side_effect=ImportError):
            self.assertFalse(missing)
            with self.assertRaises(ImportError):
                missing.value

    def test_live_button_label_does_not_inspect_model_capabilities(self):
        with patch.object(model_settings, 'list_local_models', return_value=[llm.DEFAULT_FILENAME]), \
                patch.object(model_settings, '_session_live_model', None), \
                patch.object(model_settings, 'get_setting', return_value=None), \
                patch.object(model_settings, 'model_supports_audio') as inspect:
            self.assertEqual(model_settings.live_model_for_display(), llm.DEFAULT_FILENAME)
            inspect.assert_not_called()


class EncoderLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        capabilities = Mock()
        capabilities.__enter__ = Mock(return_value=Mock(input_modalities=Mock(audio=True, vision=True)))
        capabilities.__exit__ = Mock(return_value=False)
        self.sdk = Mock(Capabilities=Mock(return_value=capabilities))
        self.engines = [Mock() for _ in range(4)]
        for engine in self.engines:
            engine.create_conversation.return_value.send_message.return_value = {'content': [{'text': 'Reply'}]}
        self.sdk.Engine.side_effect = self.engines
        patcher = patch.multiple(llm, litert_lm=self.sdk,
            get_model_path=Mock(return_value=__file__), cache_dir=Mock(return_value=Path(self.temp.name)),
            list_local_models=Mock(return_value=[llm.DEFAULT_FILENAME]),
            _engine=None, _conversation=None, _loaded_filename=None, _loaded_preference=None,
            _loaded_modalities=frozenset(), _loaded_system_prompt=llm.DEFAULT_SYSTEM_PROMPT,
            _stateful_history=[], _last_used_at=0.0,
            _supports_audio=False, _supports_vision=False, _execution={'backend': None, 'reason': ''})
        patcher.start()
        self.addCleanup(patcher.stop)
        for name, result in (('preference', 'gpu'), ('candidates', (['gpu'], ''))):
            patcher = patch.object(llm.acceleration, name, return_value=result)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_text_image_audio_text_switches_have_one_engine_and_keep_capabilities(self):
        llm.load_model()
        self.engines[0].create_conversation.assert_not_called()
        with patch.object(llm, 'record_generation'):
            llm.generate_reply('Stateful caller')
        self.assertIsNone(self.sdk.Engine.call_args.kwargs['vision_backend'])
        self.assertIsNone(self.sdk.Engine.call_args.kwargs['audio_backend'])
        with patch('App.services.attachments.build_attachment_message_parts', return_value=([], [b'image'])):
            llm._build_message('Describe', [('photo.png', 'path')])
        self.assertEqual(llm._loaded_modalities, {'vision'})
        self.engines[0].create_conversation.return_value.close.assert_called_once()
        self.engines[0].close.assert_called_once()
        self.assertIsNone(self.sdk.Engine.call_args.kwargs['audio_backend'])
        llm.prepare_voice_model(threading.Event())
        self.assertEqual(llm._loaded_modalities, {'audio', 'vision'})
        self.engines[1].close.assert_called_once()
        llm._build_message('Text again', None)
        self.assertEqual(llm._loaded_modalities, set())
        self.engines[2].close.assert_called_once()
        self.assertTrue(llm._supports_audio)
        self.assertTrue(llm._supports_vision)
        self.assertEqual(self.sdk.Engine.call_count, 4)
        llm._build_message('Next text', None)
        self.assertEqual(self.sdk.Engine.call_count, 4)
        llm.unload_model()

    def test_idle_cleanup_waits_for_quiet_period_and_next_request_can_reload(self):
        with patch.object(llm.time, 'monotonic', return_value=100):
            llm.load_model()
        with patch.object(llm.time, 'monotonic', return_value=159):
            self.assertFalse(llm.unload_if_idle())
        with patch.object(llm.time, 'monotonic', return_value=161):
            self.assertTrue(llm.unload_if_idle())
        self.engines[0].close.assert_called_once()
        self.assertFalse(llm.is_model_loaded())
        self.assertFalse(llm.unload_if_idle())
        llm.ensure_model_loaded(llm.DEFAULT_FILENAME)
        self.assertTrue(llm.is_model_loaded())
        self.assertEqual(self.sdk.Engine.call_count, 2)
        llm.unload_model()

    def test_timer_cannot_interrupt_an_active_native_operation(self):
        llm.load_model()
        locked, release = threading.Event(), threading.Event()
        def native_operation():
            with llm._model_activity():
                locked.set()
                release.wait(3)
        worker = threading.Thread(target=native_operation)
        worker.start()
        try:
            self.assertTrue(locked.wait(3))
            with patch.object(llm.time, 'monotonic', return_value=10**12):
                self.assertFalse(llm.unload_if_idle())
            self.engines[0].close.assert_not_called()
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(llm.unload_if_idle())
        llm.unload_model()

    def test_muted_live_and_cancelled_voice_start_do_not_load_audio_encoder(self):
        llm.load_model()
        llm.prepare_voice_model(threading.Event(), audio=False)
        self.assertEqual(self.sdk.Engine.call_count, 1)
        cancelled = threading.Event()
        cancelled.set()
        with self.assertRaises(llm.CancelledError):
            llm.prepare_voice_model(cancelled)
        self.assertEqual(self.sdk.Engine.call_count, 1)
        llm.unload_model()


class IdleUICleanupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = SimpleNamespace(_xopilot_can_release_model=lambda: True,
                                    _dialogs=SimpleNamespace(controls=[]))

    async def test_quiet_period_and_user_activity_delay_cache_release(self):
        with patch('App.services.runtime.time.monotonic', return_value=100) as clock, \
                patch('App.services.runtime.is_android', return_value=False), \
                patch('App.services.runtime.release_unused_memory') as release:
            cleanup = IdleMemoryCleanup()
            clock.return_value = 159
            self.assertFalse(await cleanup.poll(self.page))
            cleanup.activity()
            clock.return_value = 200
            self.assertFalse(await cleanup.poll(self.page))
            clock.return_value = 220
            self.assertTrue(await cleanup.poll(self.page))
            release.assert_called_once()
            self.assertFalse(await cleanup.poll(self.page))

    async def test_busy_request_and_open_dialog_block_even_model_release_cleanup(self):
        with patch('App.services.runtime.time.monotonic', return_value=100) as clock, \
                patch('App.services.runtime.release_unused_memory') as release:
            cleanup = IdleMemoryCleanup()
            clock.return_value = 200
            self.page._xopilot_can_release_model = lambda: False
            self.assertFalse(await cleanup.poll(self.page, model_released=True))
            self.page._xopilot_can_release_model = lambda: True
            self.page._dialogs.controls = [SimpleNamespace(open=True)]
            self.assertFalse(await cleanup.poll(self.page, model_released=True))
            release.assert_not_called()

    async def test_model_release_notifies_android_and_discards_only_thumbnail_cache(self):
        from App.app.materials import material
        module = Mock()
        with patch('App.services.runtime.is_android', return_value=True), \
                patch('App.services.runtime.release_unused_memory') as release, \
                patch('App.services.mobile_runtime.call_async', new=AsyncMock(return_value=True)) as mobile, \
                patch.object(material, '_image_preview', module):
            cleanup = IdleMemoryCleanup()
            self.assertTrue(await cleanup.poll(self.page, model_released=True))
            module.cache_clear.assert_called_once()
            mobile.assert_awaited_once_with('releaseMemory')
            release.assert_called_once()

    async def test_camera_preview_blocks_ui_cleanup_even_without_generation(self):
        self.page._xopilot_can_release_memory = lambda: False
        with patch('App.services.runtime.release_unused_memory') as release:
            self.assertFalse(await IdleMemoryCleanup().poll(self.page, model_released=True))
            release.assert_not_called()


class DialogRetentionTests(unittest.TestCase):
    def test_theme_registry_does_not_retain_closed_editor_or_payload(self):
        import flet as ft
        from App.app.theme import palette
        class Page:
            width = 393
            height = 851
            controls = []
            overlay = []
            def show_dialog(self, dialog):
                dialog.open = True
                self.current = dialog
        page = Page()
        palette.install_theme(page, 'light')
        dialog = ft.AlertDialog(content=ft.Text('editor payload'))
        reference = weakref.ref(dialog)
        page.show_dialog(dialog)
        self.assertEqual(palette.open_dialogs(page), (dialog,))
        dialog.open = False
        self.assertEqual(palette.open_dialogs(page), ())
        del page.current, dialog
        gc.collect()
        self.assertIsNone(reference())
