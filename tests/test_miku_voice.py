"""
Файл: /tests/test_miku_voice.py
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: Голоса, подготовка Miku, прогресс и отмена установки. Исполнитель: Codex.
"""

from concurrent.futures import CancelledError
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
import sys
from unittest.mock import Mock, patch

import numpy as np
from piper.voice import AudioChunk

from App.services import miku_models, miku_voice, voice_catalog, voice_installer, miku_installer


class MikuSignalTests(unittest.TestCase):
    def test_pitch_is_a_local_weighted_average_and_silence_is_unvoiced(self):
        salience = np.zeros((3, 360), dtype=np.float32)
        salience[0, 100] = 0.8
        salience[0, 101] = 0.4
        salience[0, 300] = 0.7  # Outside the local maximum's neighbourhood.
        salience[1, 0] = 0.01  # Below voicing threshold.
        salience[2, 359] = 0.9  # Boundary must not wrap to bin zero.
        f0 = miku_voice.decode_pitch(salience)
        expected = 10 * 2 ** ((1997.3794084376191 + 20 * (100 + 1 / 3)) / 1200)
        self.assertAlmostEqual(float(f0[0]), expected, places=3)
        self.assertEqual(f0[1], 0)
        self.assertAlmostEqual(float(f0[2]), 10 * 2 ** ((1997.3794084376191 + 20 * 359) / 1200), places=3)
        bins = miku_voice.coarse_pitch(np.array([0, 50, 1100, 2000], dtype=np.float32))
        np.testing.assert_array_equal(bins, [1, 1, 255, 255])

    def test_silent_mel_is_finite_with_ten_ms_frames(self):
        mel = miku_voice.log_mel(np.zeros(16000, dtype=np.float32))
        self.assertEqual(mel.shape, (1, 128, 101))
        self.assertEqual(mel.dtype, np.float32)
        np.testing.assert_allclose(mel, np.log(1e-5), atol=1e-6)

    def test_converted_chunk_replaces_cached_pcm_and_preserves_source_on_error(self):
        chunk = AudioChunk(22050, 2, 1, np.array([0.1, 0.2], dtype=np.float32), [], [])
        original = chunk.audio_int16_bytes  # Force Piper's PCM cache before conversion.
        voice = miku_voice.MikuSpeechVoice.__new__(miku_voice.MikuSpeechVoice)
        voice._converter = Mock(convert=Mock(return_value=(np.array([-0.3, 0.4], dtype=np.float32), 48000)))
        with patch.object(miku_voice.PiperSpeechVoice, "synthesize", return_value=(c for c in [chunk])):
            converted = list(voice.synthesize("Привет", threading.Event()))[0]
        self.assertEqual(converted.sample_rate, 48000)
        self.assertNotEqual(converted.audio_int16_bytes, original)
        self.assertEqual(chunk.audio_int16_bytes, original)

    def test_pending_conversion_cancels_without_loading_models(self):
        converter = miku_voice.MikuConverter()
        cancelled = threading.Event()
        cancelled.set()
        with patch.object(converter, "_load") as load:
            with self.assertRaises(CancelledError):
                converter.convert(np.zeros(100), 16000, cancelled)
            load.assert_not_called()

    def test_english_miku_name_changes_only_spoken_pronunciation(self):
        voice = miku_voice.MikuSpeechVoice.__new__(miku_voice.MikuSpeechVoice)
        voice._english = True
        text = "Hello, Miku! Mikuni is another name."
        with patch.object(miku_voice.PiperSpeechVoice, "synthesize", return_value=(c for c in [])) as source:
            cancelled = threading.Event()
            list(voice.synthesize(text, cancelled))
            source.assert_called_once_with("Hello, Meekoo! Mikuni is another name.", cancelled)
        self.assertEqual(text, "Hello, Miku! Mikuni is another name.")

    def test_cancellation_while_waiting_for_converter_does_not_leak_lock(self):
        converter = miku_voice.MikuConverter()
        converter._lock.acquire()
        cancelled = threading.Event()
        timer = threading.Timer(0.03, cancelled.set)
        timer.start()
        try:
            with self.assertRaises(CancelledError):
                converter.convert(np.zeros(100), 16000, cancelled)
            self.assertTrue(converter._lock.locked())  # Still owned by the original caller.
        finally:
            converter._lock.release()
            timer.join()


class MikuInstallationTests(unittest.TestCase):
    def test_export_component_download_progress_is_forwarded_from_pip(self):
        with tempfile.TemporaryDirectory() as directory:
            events=[]
            miku_installer._command([sys.executable,'-c',
                'import time; print("Progress 0 of 100",flush=True); time.sleep(.2); print("Progress 50 of 100",flush=True); time.sleep(.2)'],
                Path(directory)/'install.log',directory,on_download=events.append)
            self.assertIn(50,[event.downloaded for event in events])
            self.assertTrue(all(event.total==100 for event in events))

    def test_export_command_cancellation_stops_child(self):
        import time
        with tempfile.TemporaryDirectory() as directory:
            cancelled=threading.Event();timer=threading.Timer(.1,cancelled.set)
            timer.start();start=time.monotonic()
            try:
                with self.assertRaises(CancelledError):
                    miku_installer._command([sys.executable,'-c','import time; time.sleep(30)'],
                        Path(directory)/'install.log',directory,cancelled=cancelled)
            finally:timer.join()
            self.assertLess(time.monotonic()-start,3)

    def test_embedded_launcher_is_not_executed_as_a_python_venv(self):
        import os
        from App.services import voice_runtime
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(miku_installer, "app_data_dir", return_value=Path(directory)), \
                patch.dict(os.environ, {}, clear=True), \
                patch.object(miku_installer.sys, "executable", str(Path(directory) / "Xopilot")), \
                patch.object(miku_installer.venv, "EnvBuilder") as builder, \
                patch.object(voice_runtime,'export_runtime',return_value=Path(directory)/'portable-python') as runtime, \
                patch.object(miku_installer,'_command',side_effect=lambda *a,**k:(Path(directory)/'runtime/miku-export').mkdir(exist_ok=True)) as command:
            result=miku_installer._export_python(Mock())
            self.assertTrue(str(result).endswith('python.exe' if os.name=='nt' else 'bin/python'))
            runtime.assert_called_once()
            self.assertEqual(command.call_args_list[0].args[0][0],str(Path(directory)/'portable-python'))
            builder.assert_not_called()

    def test_download_reports_bytes_verifies_and_cancels_without_replacing_model(self):
        payload=b'x'*(1024*1024+5)
        class Response(io.BytesIO):
            headers={'Content-Length':str(len(payload))}
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'model.onnx';events=[]
            with patch.object(voice_installer.urllib.request,'urlopen',return_value=Response(payload)):
                voice_installer.download_verified('https://example.invalid/model',target,
                    hashlib.sha256(payload).hexdigest(),on_download=events.append)
            downloaded=[event for event in events if event.phase=='download']
            self.assertEqual([e.downloaded for e in downloaded],[0,*range(65536,len(payload),65536),len(payload)])
            self.assertEqual(events[-1].phase,'ready')
            self.assertTrue(all(e.total==len(payload) for e in downloaded))
            cancelled=threading.Event()
            def cancel(event):
                if event.phase=='download' and event.downloaded:cancelled.set()
            with patch.object(voice_installer.urllib.request,'urlopen',return_value=Response(payload)):
                with self.assertRaises(CancelledError):
                    voice_installer.download_verified('https://example.invalid/model',target,'0'*64,
                                                     on_download=cancel,cancelled=cancelled)
            self.assertEqual(target.read_bytes(),payload)
            self.assertEqual(list(Path(directory).iterdir()),[target])

    def test_packaged_export_sources_match_sources_and_do_not_depend_on_app_pyc(self):
        from App.services.voice_runtime import stage_export_sources
        with tempfile.TemporaryDirectory() as directory:
            root=stage_export_sources(Path(directory)/'source')
            original=Path(miku_installer.__file__).parent/'_rvc_export'
            for path in original.iterdir():
                if path.suffix=='.py':
                    # Staging writes UTF-8/LF; Windows Git checkout may use CRLF.
                    self.assertEqual((root/'_rvc_export'/path.name).read_text(encoding='utf-8'),
                                     path.read_text(encoding='utf-8'))
            self.assertTrue((root/'_rvc_export/LICENSE.rvc').is_file())

    def test_invalid_metadata_and_corrupted_encoder_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(miku_models, "model_directory", return_value=Path(directory)), \
                patch.object(miku_voice, "model_directory", return_value=Path(directory)):
            root = Path(directory)
            (root / "miku.json").write_text("[]")
            self.assertFalse(miku_models.miku_installed())
            (root / "miku.json").write_text(json.dumps({
                "format": 1, "version": "v2", "checkpoint_sha256": miku_models.CHECKPOINT_SHA256,
                "onnx_sha256": "invalid", "parity": [{}, {}, {}], "sample_rate": 48000,
                "hop": 480, "inter_channels": 192, "speaker_id": 0,
            }))
            for name in ("miku.onnx", "contentvec.onnx", "rmvpe.onnx"):
                (root / name).write_bytes(b"corrupted")
            import onnxruntime
            with patch.object(onnxruntime, "InferenceSession") as load:
                with self.assertRaisesRegex(RuntimeError, "повреждена"):
                    miku_voice.MikuConverter()._load(threading.Event())
                load.assert_not_called()

    def test_export_interpreter_keeps_virtual_environment_symlink(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "system-python"
            base.touch()
            environment_python = Path(directory) / "venv-python"
            try:
                environment_python.symlink_to(base)
            except OSError:
                self.skipTest("Creating symlinks requires extra permission on this platform.")
            with patch.dict(os.environ, {"XOPILOT_RVC_EXPORT_PYTHON": str(environment_python)}):
                self.assertEqual(miku_installer._export_python(Mock()), environment_python)

    def test_piper_files_alone_never_mark_miku_installed(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(miku_models, "model_directory", return_value=Path(directory)), \
                patch.object(voice_catalog.VoiceModel, "installed", new_callable=lambda: property(lambda _: True)):
            self.assertFalse(voice_catalog.VOICES["miku"].installed)
            self.assertTrue(voice_catalog.VOICES["cove"].installed)
            self.assertTrue(voice_catalog.VOICES["maple"].installed)

    def test_bad_download_preserves_previous_model_and_removes_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "model.onnx"
            target.write_bytes(b"existing")
            with patch.object(voice_installer.urllib.request, "urlopen", return_value=io.BytesIO(b"bad")):
                with self.assertRaisesRegex(RuntimeError, "Контрольная сумма"):
                    voice_installer.download_verified("https://example.invalid/model", target,
                                                      hashlib.sha256(b"valid").hexdigest())
            self.assertEqual(target.read_bytes(), b"existing")
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_matching_download_does_not_use_network(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "model.onnx"
            target.write_bytes(b"valid")
            with patch.object(voice_installer.urllib.request, "urlopen") as request:
                voice_installer.download_verified("https://example.invalid/model", target,
                                                  hashlib.sha256(b"valid").hexdigest())
                request.assert_not_called()


class VoiceInstallUITests(unittest.IsolatedAsyncioTestCase):
    async def test_progress_is_visible_in_selected_voice_card_and_cancel_works(self):
        import asyncio
        import flet as ft
        from App.settings.models import main as settings
        page=Mock()
        page.run_task=lambda function,*args:asyncio.create_task(function(*args))
        started=threading.Event()
        def install(identifier,on_progress,*,on_download,cancelled):
            on_download(voice_installer.DownloadProgress('voice.onnx',50,100))
            started.set()
            if not cancelled.wait(2):raise AssertionError('UI cancellation was not delivered')
            raise CancelledError()
        root=settings.build_models_page(page,Mock())
        cards=[c for c in root.controls if isinstance(c,ft.Column) and len(c.controls)==5
               and isinstance(c.controls[1],ft.ProgressBar)]
        self.assertEqual(len(cards),3)
        card,bar,label,cancel,feedback=cards[1].controls
        with patch.object(settings,'install_voice',side_effect=install):
            pending=asyncio.create_task(card.content.controls[-1].on_click(None))
            self.assertTrue(await asyncio.to_thread(started.wait,1))
            await asyncio.sleep(.01)
            self.assertTrue(bar.visible)
            self.assertEqual(bar.value,.5)
            self.assertIn('50%',label.value)
            cancel.on_click(None)
            await pending
        self.assertFalse(bar.visible)
        self.assertIn('отменена',feedback.value)


if __name__ == "__main__":
    unittest.main()
