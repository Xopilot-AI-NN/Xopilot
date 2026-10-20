"""
Файл: /tests/test_remote_transport.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Настоящий HTTP-обмен телефон → ПК на изолированном QA-сервере.
          Исполнитель: Codex. Требует тестового сервера с почтовым перехватчиком.
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path
import unittest
import uuid
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from App.services import remote_tasks


@unittest.skipUnless(os.environ.get('XOPILOT_REMOTE_QA_URL'),'Изолированный QA-сервер не запущен')
class RemoteTransportTests(unittest.TestCase):
    def test_encrypted_job_approval_result_revocation_and_foreign_account(self):
        if not os.environ.get('XOPILOT_TEST_DATABASE_URL','').endswith('/xopilot_test'):
            self.skipTest('Для выдачи QA-подписки нужна изолированная БД xopilot_test')
        base=os.environ['XOPILOT_REMOTE_QA_URL']
        self.assertTrue(base.startswith('http://127.0.0.1:'))
        def api(path,token=None,body=None,method=None):
            req=Request(base+'/api/v1'+path,data=json.dumps(body).encode() if body is not None else None,
                method=method or ('POST' if body is not None else 'GET'),
                headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
            with urlopen(req,timeout=15) as response:return json.load(response)
        def register():
            email='qa_'+uuid.uuid4().hex+'@example.invalid';password='QA only strong password 123!'
            pending=api('/auth/register',body=dict(username='Remote QA',email=email,password=password,device_name='Телефон QA'))
            path=Path(os.environ['XOPILOT_REMOTE_QA_MAIL'])/hashlib.sha256(email.encode()).hexdigest()
            session=api('/auth/verify-email',body={'registration_id':pending['registration_id'],'code':path.read_text()})
            return email,password,session
        email,password,phone=register()
        pc=api('/auth/login',body=dict(email=email,password=password,device_name='ПК QA'))
        _,_,foreign=register()
        pt,ct,ft=phone['access_token'],pc['access_token'],foreign['access_token']
        pid,cid=phone['session_id'],pc['session_id']
        owner=phone['account_id'];key=os.urandom(32)
        def crypt(method,identifier,kind,value):
            with patch.object(remote_tasks,'credentials',return_value=({'account_id':owner},key)):
                return getattr(remote_tasks,method)(identifier,kind,value)
        api('/remote/hosts',ct,dict(enabled=True,senders=[pid]),'PUT')
        hosts=api('/remote/hosts',pt)['hosts'];self.assertIn(cid,[h['session_id'] for h in hosts])
        self.assertEqual(api('/remote/hosts',ft)['hosts'],[])
        identifier=str(uuid.uuid4());payload=dict(version=1,id=identifier,sender=pid,target=cid,prompt='Проверка связи')
        envelope=crypt('encode',identifier,'task',payload)
        body=dict(id=identifier,target=cid,task=envelope)
        with self.assertRaises(HTTPError) as unpaid:api('/remote/jobs',pt,body)
        self.assertEqual(unpaid.exception.code,402);unpaid.exception.close()
        fixture=os.environ.get('XOPILOT_REMOTE_QA_SERVER','/home/developer/Xopiser/xopilot-backend/target/debug/examples/qa_server')
        subprocess.run([fixture,'--grant-test-plan',str(uuid.UUID(owner)),'elite'],check=True,capture_output=True)
        api('/remote/jobs',pt,body);api('/remote/jobs',pt,body)
        jobs=api('/remote/inbox',ct)['jobs'];job=next(j for j in jobs if j['id']==identifier)
        self.assertEqual(crypt('decode',identifier,'task',job['task']),payload)
        api('/remote/jobs/'+identifier+'/claim',ct,{})
        with self.assertRaises(HTTPError) as error:api('/remote/jobs/'+identifier,ft)
        self.assertEqual(error.exception.code,404);error.exception.close()
        question=str(uuid.uuid4());request=dict(kind='command',argv=['python','--version'],cwd='QA')
        value=dict(request=request,question=question)
        api('/remote/jobs/'+identifier+'/result',ct,dict(state='approval',question=question,result=crypt('encode',identifier,'result',value)),'PUT')
        decision=dict(question=question,request_hash=hashlib.sha256(remote_tasks.canonical(request)).hexdigest(),approved=True)
        api('/remote/jobs/'+identifier+'/decision',pt,dict(question=question,decision=crypt('encode',identifier,'decision:'+question,decision)))
        received=api('/remote/jobs/'+identifier,ct)
        self.assertEqual(crypt('decode',identifier,'decision:'+question,received['decision']),decision)
        result=dict(reply='Связь проверена')
        api('/remote/jobs/'+identifier+'/result',ct,dict(state='completed',result=crypt('encode',identifier,'result',result)),'PUT')
        received=api('/remote/jobs/'+identifier,pt)
        self.assertEqual(received['state'],'completed')
        self.assertEqual(crypt('decode',identifier,'result',received['result']),result)
        api('/remote/hosts',ct,dict(enabled=False,senders=[]),'PUT')
        self.assertEqual(api('/remote/hosts',pt)['hosts'],[])
        with self.assertRaises(HTTPError) as error:api('/remote/jobs',pt,dict(id=str(uuid.uuid4()),target=cid,task=envelope))
        error.exception.close()
