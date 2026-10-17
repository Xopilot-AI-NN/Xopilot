"""Файл: /tests/test_model_context.py
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: Метаданные окон и настоящий HTTP-перенос сжатого контекста.
"""
import copy
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch
from App.services import model_context, api_chat, context_budget


class ContextMetadataTests(unittest.TestCase):
    def setUp(self):
        model_context._cache.clear()
        context_budget._summaries.clear()

    def test_public_openrouter_catalog_does_not_receive_key_or_history(self):
        config = dict(url='https://openrouter.ai/api/v1', model='org/model', key='test-secret')
        conn = Mock()
        conn.getresponse.return_value.status = 200
        conn.getresponse.return_value.read.return_value = json.dumps({'data': [
            {'id': 'org/model', 'context_length': 131072,
             'top_provider': {'max_completion_tokens': 8192}}]}).encode()
        with patch.object(model_context.http.client, 'HTTPSConnection', return_value=conn) as connect:
            engine = model_context.engine(config)
            self.assertIs(model_context.engine(config), engine)
        self.assertEqual(engine.max_num_tokens, 131072)
        self.assertEqual(engine.max_output_tokens, 8192)
        self.assertNotIn('test-secret', str(conn.request.call_args))
        connect.assert_called_once()

    def test_google_metadata_uses_google_host_and_key_header(self):
        config = dict(url='https://generativelanguage.googleapis.com/v1beta/openai',
                      model='models/gemini-test', key='test-secret')
        conn = Mock()
        conn.getresponse.return_value.status = 200
        conn.getresponse.return_value.read.return_value = b'{"inputTokenLimit": 1048576, "outputTokenLimit": 65536}'
        with patch.object(model_context.http.client, 'HTTPSConnection', return_value=conn) as connect:
            engine = model_context.engine(config)
        self.assertEqual(engine.max_num_tokens, 1048576)
        self.assertEqual(engine.max_output_tokens, 65536)
        self.assertEqual(connect.call_args.args[0], 'generativelanguage.googleapis.com')
        self.assertEqual(conn.request.call_args.args, ('GET', '/v1beta/models/gemini-test'))
        self.assertNotIn('test-secret', conn.request.call_args.args[1])

    def test_unknown_provider_is_not_assigned_an_invented_limit(self):
        config = dict(url='https://custom.example/v1', model='m', key='k')
        with patch.object(model_context.http.client, 'HTTPSConnection') as connect:
            self.assertIsNone(model_context.engine(config))
            connect.assert_not_called()
        self.assertEqual(model_context.learn_error(config,
            'maximum context length is 4,096 tokens, request has 9000'), 4096)
        self.assertEqual(model_context.engine(config).max_num_tokens, 4096)
        self.assertIsNone(model_context.learn_error(config, 'request has 9000 tokens'))

    def test_transport_learns_limit_compacts_with_same_model_and_preserves_original(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(body)
                if len(requests) == 1:
                    self.send_response(400); self.end_headers()
                    self.wfile.write(b'{"error":{"message":"maximum context length is 4096 tokens"}}')
                    return
                text = ('Name Denis; project Xopilot; commands require approval.'
                        if 'max_tokens' in body else 'Denis; Xopilot; confirmation required.')
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({'choices':[{'message':{'content':text}}]}).encode())
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        config = dict(url=f'http://127.0.0.1:{server.server_port}/v1', model='same-model', key='test-only')
        history = [{'role':'user', 'content':'My name is Denis. Project Xopilot. Do not run commands without approval.'}]
        history += [{'role':'ai', 'content':'Filler ' * 500} for _ in range(10)]
        original = copy.deepcopy(history)
        try:
            with patch.object(api_chat, 'configuration', return_value=config), patch.object(api_chat, 'record_generation') as stats:
                result = api_chat.generate_reply('What is my name?', history=history)
            self.assertIn('Denis', result)
            self.assertEqual(history, original)
            self.assertTrue(any('max_tokens' in r for r in requests))
            self.assertTrue(all(r['model'] == 'same-model' for r in requests))
            self.assertLess(len(json.dumps(requests[-1])), len(json.dumps(requests[0])) // 3)
            self.assertNotIn('max_tokens', requests[-1])
            stats.assert_called_once()
        finally:
            server.shutdown(); server.server_close(); thread.join()
