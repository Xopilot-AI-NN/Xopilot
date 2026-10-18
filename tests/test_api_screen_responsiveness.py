"""Файл: /tests/test_api_screen_responsiveness.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Медленный настоящий HTTP, отмена и отказ API от кадров экрана.
"""
import asyncio
from concurrent.futures import CancelledError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import patch
from App.services import api_chat


class ScreenApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests = []
        self.started = threading.Event()
        self.release = threading.Event()
        self.slow = False
        self.status = 400
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.requests.append(data)
                image = isinstance(data['messages'][-1]['content'], list)
                if image and owner.slow:
                    owner.started.set()
                    owner.release.wait(3)
                body = ({'error': {'message': 'This model does not support image input'}} if image else
                        {'choices': [{'message': {'content': 'Прочитал controls.'}}]})
                raw = json.dumps(body).encode()
                try:
                    self.send_response(owner.status if image else 200)
                    self.send_header('Content-Length', str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError): pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.config = {'url': f'http://127.0.0.1:{self.server.server_port}/v1', 'model': 'qa', 'key': ''}
        for p in (patch.object(api_chat, 'configuration', return_value=self.config),
                  patch.object(api_chat, 'record_generation'),
                  patch.object(api_chat, '_image_rejected', set()),
                  patch.object(api_chat, '_screen_fallback_until', {}),
                  patch.object(api_chat, 'build_attachment_message_parts',
                               side_effect=lambda files: ([], [b'\xff\xd8\xfftest'] if files else []))):
            p.start(); self.addCleanup(p.stop)

    async def asyncTearDown(self):
        self.release.set()
        await asyncio.to_thread(self.server.shutdown)
        self.server.server_close()
        self.worker.join()

    async def test_unsupported_screen_falls_back_once_and_remembers_capability(self):
        files = [('screen.png', '/qa/screen.png')]
        answer = await asyncio.to_thread(api_chat.generate_reply, 'Посмотри экран',
            attachments=files, screen_attachments=files, structured=True)
        self.assertEqual(answer, 'Прочитал controls.')
        self.assertEqual(len(self.requests), 2)
        self.assertNotIsInstance(self.requests[-1]['messages'][-1]['content'], list)
        with self.assertRaisesRegex(RuntimeError, 'не поддерживает изображения'):
            await asyncio.to_thread(api_chat.generate_reply, 'Фото', attachments=files)
        self.assertEqual(len(self.requests), 2)

    async def test_screen_500_does_not_repeat_image_with_another_json_format(self):
        self.status = 500
        files = [('screen.png', '/qa/screen.png')]
        self.assertEqual(await asyncio.to_thread(api_chat.generate_reply, 'Экран',
            attachments=files, screen_attachments=files, structured=True), 'Прочитал controls.')
        self.assertEqual(len(self.requests), 2)
        self.assertIsNone(api_chat.image_support(self.config), 'A generic 500 does not prove missing vision')

    async def test_slow_image_request_leaves_loop_responsive_and_can_be_cancelled(self):
        self.slow = True
        cancelled = threading.Event()
        task = asyncio.create_task(asyncio.to_thread(api_chat.generate_reply, 'Экран',
            attachments=[('screen.png', '/qa/screen.png')], cancelled=cancelled))
        try:
            self.assertTrue(await asyncio.to_thread(self.started.wait, 2))
            ticks = 0
            for _ in range(10):
                await asyncio.sleep(.01)
                ticks += 1
            self.assertEqual(ticks, 10)
            cancelled.set()
            with self.assertRaises((CancelledError, asyncio.CancelledError)):
                await asyncio.wait_for(task, 1)
        finally:
            cancelled.set(); self.release.set()
            await asyncio.gather(task, return_exceptions=True)
