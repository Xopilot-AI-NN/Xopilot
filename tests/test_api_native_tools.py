"""Файл: /tests/test_api_native_tools.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Настоящий HTTP: нативные функции, ID результатов, fallback и префикс API.
"""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from App.services import api_chat, api_tools, agent_protocol


class NativeApiTests(unittest.TestCase):
    def setUp(self):
        self.requests=[];self.responses=[];owner=self
        class Handler(BaseHTTPRequestHandler):
            server_version='llama.cpp'
            def log_message(self,*a):pass
            def do_POST(self):
                owner.requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                status, body = owner.responses.pop(0)
                data=json.dumps(body).encode()
                self.send_response(status);self.send_header('Content-Length',str(len(data)));self.end_headers()
                self.wfile.write(data)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=self.server.serve_forever,daemon=True);worker.start()
        self.addCleanup(worker.join);self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        config={'url':f'http://127.0.0.1:{self.server.server_port}/v1','model':'qa','key':''}
        for p in [patch.object(api_chat,'configuration',return_value=config),
                  patch.object(api_chat,'record_generation'),patch.object(api_chat,'_tools_unsupported',set()),
                  patch.object(api_chat,'_empty_reasoning',set()),
                  patch.object(api_chat,'_llama_servers',set()),patch.object(api_chat,'_cache_usage',{}),
                  patch('App.services.model_context.engine',return_value=None)]:
            p.start();self.addCleanup(p.stop)
        self.tools=agent_protocol.native_tools({'search_library':{'query':'search words'}})

    def reply(self, **message):
        return (200,{'choices':[{'message':message}]})

    def call(self, **kwargs):
        return api_chat.generate_reply('Найди бюджет',instructions='stable',native_tools=self.tools,**kwargs)

    def test_parallel_calls_keep_ids_and_results_without_repeating_or_using_json_mode(self):
        calls=[{'id':str(i),'type':'function','function':{'name':'search_library',
                'arguments':json.dumps({'query':q})}} for i,q in enumerate(['budget','cost'])]
        self.responses=[self.reply(content='Ищу документы',tool_calls=calls), self.reply(content='Бюджет — 42.')]
        reply=self.call()
        parsed=json.loads(reply)
        self.assertEqual(len(parsed['actions']),2)
        outputs=api_tools.results(reply,[{'text':'budget 42'},{'text':'cost 12'}])
        final=self.call(history=[{'role':'user','content':'Найди бюджет'}, {'role':'ai','content':reply}],tool_results=outputs)
        self.assertEqual(json.loads(final),{'final':'Бюджет — 42.'})
        sent=self.requests[-1]
        self.assertNotIn('response_format',sent)
        self.assertEqual([m['role'] for m in sent['messages']],['system','user','assistant','tool','tool'])
        self.assertEqual(sent['messages'][2]['tool_calls'],calls)
        self.assertEqual([m['tool_call_id'] for m in sent['messages'][-2:]],['0','1'])
        self.assertTrue(sent['cache_prompt'])
        self.assertEqual(self.requests[0]['messages'][0],sent['messages'][0])

    def test_explicit_unsupported_functions_retry_setup_only_in_legacy_format(self):
        self.responses=[(400,{'error':{'message':'tools are not supported'}}),
                        self.reply(content='{"tool":"search_library","arguments":{"query":"budget"}}')]
        reply=self.call(structured=True)
        self.assertEqual(json.loads(reply)['tool'],'search_library')
        self.assertEqual(len(self.requests),2)
        self.assertNotIn('tools',self.requests[-1])
        self.assertEqual(self.requests[-1]['response_format'],{'type':'json_object'})

    def test_unknown_function_and_duplicate_ids_are_rejected_before_execution(self):
        for name,ids in [('delete_everything',['a']),('search_library',['a','a'])]:
            with self.subTest(name=name):
                self.responses=[self.reply(content=None,tool_calls=[{'id':i,'type':'function',
                    'function':{'name':name,'arguments':'{"query":"x"}'}} for i in ids])]
                with self.assertRaises(RuntimeError):self.call()

    def test_plain_chat_keeps_history_prefix_and_sends_no_vendor_fields_until_identified(self):
        self.responses=[self.reply(content='Первый'),self.reply(content='Второй')]
        first=api_chat.generate_reply('Первый запрос',instructions='stable')
        api_chat.generate_reply('Следующий',instructions='stable',history=[
            {'role':'user','content':'Первый запрос'},{'role':'ai','content':first}])
        self.assertNotIn('cache_prompt',self.requests[0])
        self.assertNotIn('tools',self.requests[0])
        self.assertEqual(self.requests[0]['messages'],self.requests[1]['messages'][:2])

    def test_native_and_local_schemas_ground_read_ids_in_observed_results(self):
        tools={'read_material':{'id':'observed ID or unique name'}}
        refs={'366216f6dd2a13ee','Проверка KV.md'}
        definitions=agent_protocol.native_tools(tools,material_refs=refs)
        parameter=definitions[0]['function']['parameters']['properties']['id']
        self.assertEqual(set(parameter['enum']),refs)
        self.assertNotIn('3626f6dd2a13ee',parameter['enum'])
        self.assertEqual(parameter['description'],'observed ID or unique name')

    def test_reasoning_only_reply_retries_generation_without_exposing_reasoning(self):
        self.responses=[self.reply(content='',reasoning_content='INTERNAL_ONLY'),
                        self.reply(content='Итоговый ответ')]
        answer=self.call()
        self.assertEqual(json.loads(answer),{'final':'Итоговый ответ'})
        self.assertEqual(len(self.requests),2)
        self.assertEqual(self.requests[-1]['chat_template_kwargs'],{'enable_thinking':False})
        self.assertEqual(self.requests[-1]['reasoning_effort'],'none')

    def test_repeated_reasoning_only_reply_stops_after_one_generation_retry(self):
        from App.services.task_control import EmptyModelReplyError
        self.responses=[self.reply(content='',reasoning_content='INTERNAL_ONLY') for _ in range(2)]
        with self.assertRaises(EmptyModelReplyError):self.call()
        self.assertEqual(len(self.requests),2)
