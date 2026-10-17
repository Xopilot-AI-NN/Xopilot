"""Real HTTP resume, pause, disconnect and integrity gates without large models."""
import hashlib
import threading
import unittest
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from App.services import model_installer as installer


class ModelDownloadTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.payload = b'Model-test-bytes-' * 100000
        self.requests = []
        self.truncate = False
        self.ignore_range = False
        self.auto_restore = False
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append(dict(self.headers))
                start = int(self.headers.get('Range', 'bytes=0-')[6:].split('-')[0])
                if owner.ignore_range:
                    start = 0
                if start == len(owner.payload):
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{start}')
                    self.end_headers()
                    return
                self.send_response(206 if start else 200)
                self.send_header('Content-Length', str(len(owner.payload) - start))
                self.send_header('ETag', '"fixture-v1"')
                if start:
                    self.send_header('Content-Range', f'bytes {start}-{len(owner.payload)-1}/{len(owner.payload)}')
                self.end_headers()
                end = start + 512 * 1024 if owner.truncate else len(owner.payload)
                if owner.auto_restore:
                    owner.truncate = False
                try:
                    self.wfile.write(owner.payload[start:end])
                except (BrokenPipeError, ConnectionResetError):
                    pass
            def log_message(self, *args):
                pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.model = replace(installer.GEMMA_4_E2B,
            filename='test.litertlm', download_url=f'http://127.0.0.1:{self.server.server_port}/model',
            sha256=hashlib.sha256(self.payload).hexdigest())
        self.patches = [patch.object(installer, 'MODELS_DIR', Path(self.folder.name)),
                        patch.dict(installer.DOWNLOADABLE_MODELS, {self.model.id: self.model})]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_pause_retains_bytes_then_new_job_continues_range_and_verifies(self):
        pause = threading.Event()
        notices = []
        def progress(downloaded, total, state):
            notices.append((downloaded, total, state))
            if downloaded:
                pause.set()
        # Progress is throttled; simulate enough elapsed time to observe every chunk.
        with patch.object(installer.time, 'monotonic', side_effect=range(100)):
            with self.assertRaises(installer.DownloadPaused):
                installer.install_model(self.model.id, progress=progress, pause=pause)
        part = installer.partial_path(self.model)
        offset = part.stat().st_size
        self.assertGreater(offset, 0)
        self.assertFalse(self.model.path.exists())
        installer.install_model(self.model.id)
        self.assertEqual(self.requests[-1]['Range'], f'bytes={offset}-')
        self.assertEqual(self.requests[-1]['If-Range'], '"fixture-v1"')
        self.assertEqual(self.model.path.read_bytes(), self.payload)
        self.assertFalse(part.exists())
        self.assertEqual(notices[0][2], 'downloading')

    def test_disconnect_preserves_partial_and_server_ignoring_range_restarts_safely(self):
        self.truncate = True
        with self.assertRaises(installer.DownloadInterrupted):
            installer.install_model(self.model.id)
        self.assertEqual(installer.partial_path(self.model).stat().st_size, 512 * 1024)
        self.truncate = False
        self.ignore_range = True
        installer.install_model(self.model.id)
        self.assertEqual(self.model.path.read_bytes(), self.payload)

    def test_hash_failure_preserves_installed_model_and_removes_corrupt_partial(self):
        self.model.path.write_bytes(b'previous verified model')
        bad = replace(self.model, sha256='f' * 64)
        with patch.dict(installer.DOWNLOADABLE_MODELS, {bad.id: bad}):
            with self.assertRaisesRegex(RuntimeError, 'SHA-256'):
                installer.install_model(bad.id)
        self.assertEqual(self.model.path.read_bytes(), b'previous verified model')
        self.assertFalse(installer.partial_path(self.model).exists())

    def test_network_job_wait_can_be_paused_and_resumed(self):
        self.truncate = True
        job = installer.ModelDownload(self.model.id)
        waiting = threading.Event()
        def wait_for_retry(seconds):
            waiting.set()
            return True
        with patch.object(job.pause_requested, 'wait', side_effect=wait_for_retry):
            job.start()
            self.assertTrue(waiting.wait(3))
            job.worker.join(3)
        self.assertEqual(job.state, 'paused')
        self.truncate = False
        job.start()
        job.worker.join(3)
        self.assertEqual(job.state, 'installed')
        self.assertEqual(self.model.path.read_bytes(), self.payload)

    def test_job_automatically_resumes_after_network_returns(self):
        self.truncate = True
        self.auto_restore = True
        job = installer.ModelDownload(self.model.id)
        def stop():
            job.pause()
            if job.worker:
                job.worker.join(3)
        self.addCleanup(stop)
        job.start()
        job.worker.join(15)
        self.assertEqual(job.state, 'installed', job.error)
        self.assertEqual(self.requests[1]['Range'], 'bytes=524288-')
        self.assertEqual(self.model.path.read_bytes(), self.payload)

class ModelImportTests(unittest.TestCase):
    def test_corrupt_import_preserves_installed_model_and_valid_import_is_atomic(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'usb.litertlm';source.write_bytes(b'valid model')
            dest=root/'models';dest.mkdir();target=dest/installer.GEMMA_4_E2B.filename
            target.write_bytes(b'previous installed model')
            model=replace(installer.GEMMA_4_E2B,sha256=hashlib.sha256(b'valid model').hexdigest())
            with patch.object(installer,'MODELS_DIR',str(dest)),patch.dict(installer.DOWNLOADABLE_MODELS,{model.id:model},clear=True):
                source.write_bytes(b'corrupted')
                with self.assertRaisesRegex(ValueError,'SHA-256'):installer.import_model(model.filename,path=str(source))
                self.assertEqual(target.read_bytes(),b'previous installed model')
                source.write_bytes(b'valid model')
                self.assertEqual(installer.import_model(model.filename,path=str(source)),str(target))
                self.assertEqual(target.read_bytes(),b'valid model')
                self.assertEqual(source.read_bytes(),b'valid model')
