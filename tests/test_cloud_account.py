import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch
from App.services import cloud_account as cloud


class AccountTests(unittest.TestCase):
    def test_google_avatar_download_never_sends_credentials_and_is_bounded(self):
        response=Mock();response.read.return_value=b'synthetic image';context=Mock()
        context.__enter__=Mock(return_value=response);context.__exit__=Mock(return_value=False)
        opener=Mock();opener.open.return_value=context
        with patch.object(cloud,'build_opener',return_value=opener),patch('App.services.cloud_traffic.reserve'),patch('App.services.profile.normalize_avatar',return_value='avatar'):
            self.assertEqual(cloud._download_google_avatar('https://lh3.googleusercontent.com/a'),'avatar')
            request=opener.open.call_args.args[0]
            self.assertIsNone(request.get_header('Authorization'));self.assertIsNone(request.get_header('Cookie'))
            response.read.return_value=b'x'*(2*1024*1024+1)
            with self.assertRaises(ValueError):cloud._download_google_avatar('https://lh3.googleusercontent.com/a')
        for url in ['http://lh3.googleusercontent.com/a','https://127.0.0.1/a','https://lh3.googleusercontent.com.attacker.invalid/a',
                    'https://user:password@lh3.googleusercontent.com/a','https://lh3.googleusercontent.com:123/a']:
            with patch.object(cloud,'build_opener') as builder,self.assertRaises(ValueError):
                cloud._download_google_avatar(url)
            builder.assert_not_called()
    def test_google_login_imports_profile_and_photo_failure_keeps_session(self):
        from App.services import profile
        def cas(expected,updates):
            if any(self.settings.get(k)!=v for k,v in expected):return False
            self.settings.update(updates);return True
        self.db.apply_sync_settings.side_effect=cas
        tokens=dict(account_id='owner',session_id='device',access_token='secret token',refresh_token='refresh',expires_in=900)
        info=dict(username='Google name',display_name='Google name',email='qa@example.invalid',google_linked=True,
                  google_profile={'name':'Google name','picture_url':'https://lh3.googleusercontent.com/a'})
        with patch.object(cloud,'_request',return_value=info),patch.object(cloud,'_download_google_avatar',side_effect=OSError('offline')):
            cloud._persist_login('https://xopilot.by',tokens)
        self.assertEqual(profile.read(self.db)['name'],'Google name')
        self.assertEqual(profile.read(self.db)['avatar'],'')
        self.assertTrue(cloud.state()['google_linked'])
        self.assertIn('Фото Google',cloud.state()['google_profile_warning'])
        self.assertEqual(json.loads(self.settings[cloud.KEY])['access_token'],'secret token')
        with patch.object(profile,'get_db',return_value=self.db):profile.update(name='Custom name')
        with patch.object(cloud,'_request',return_value=info),patch.object(cloud,'_download_google_avatar',side_effect=OSError('offline')):
            cloud.refresh_google_profile()
        self.assertEqual(profile.read(self.db)['name'],'Custom name')
    def test_google_profile_refresh_retains_rotated_credentials(self):
        saved=self.session();saved['google_linked']=True;cloud._save(saved)
        rotated=dict(account_id='owner',session_id='device',access_token='rotated access',refresh_token='rotated refresh',expires_in=900)
        info={'google_profile':{'name':'Google name','picture_url':''}}
        with patch.object(cloud,'_request',side_effect=[rotated,info]):cloud.refresh_google_profile()
        fresh=json.loads(self.settings[cloud.KEY])
        self.assertEqual(fresh['access_token'],'rotated access');self.assertEqual(fresh['refresh_token'],'rotated refresh')
    def setUp(self):
        self.settings = {}
        self.db = Mock()
        self.db.get_setting.side_effect = self.settings.get
        self.db.set_setting.side_effect = self.settings.__setitem__
        self.patcher = patch.object(cloud, 'get_db', return_value=self.db)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def session(self):
        return {'account_id': 'owner', 'session_id': 'device', 'username': 'qa', 'display_name': 'QA',
                'endpoint': 'https://xopilot.by', 'device_name': 'QA device', 'expires_at': 0,
                'access_token': 'old access', 'refresh_token': 'old refresh'}

    def test_credentials_are_hidden_from_ui_and_chat_content_not_read(self):
        tokens = dict(account_id='owner', session_id='device', access_token='secret token', refresh_token='refresh', expires_in=900)
        with patch.object(cloud, '_request', side_effect=[tokens, {'username':'qa', 'display_name':'QA', 'email':'qa@example.invalid'}]):
            state = cloud.sign_in('qa@example.invalid', 'A strong QA password')
        self.assertNotIn('access_token', state)
        self.assertNotIn('refresh_token', state)
        self.assertNotIn('A strong QA password', self.settings[cloud.KEY])
        self.db.list_chats.assert_not_called()
        self.db.get_messages.assert_not_called()

    def test_failed_storage_is_not_reported_as_successful_signin(self):
        self.db.set_setting.side_effect = RuntimeError('disk full')
        tokens = dict(account_id='owner', session_id='device', access_token='token', refresh_token='refresh', expires_in=900)
        with patch.object(cloud, '_request', side_effect=[tokens, {'username':'qa', 'display_name':'QA', 'email':'qa@example.invalid'}]):
            with self.assertRaises(RuntimeError):
                cloud.sign_in('qa@example.invalid', 'A strong QA password')
        self.assertIsNone(cloud.state())

    def test_revoked_refresh_removes_saved_session(self):
        cloud._save(self.session())
        with patch.object(cloud, '_request', side_effect=cloud.CloudError('invalid_session',401)):
            with self.assertRaises(cloud.CloudError):
                cloud.sessions()
        self.assertIsNone(cloud.state())

    def test_network_failure_does_not_silently_leave_server_session_active(self):
        saved = self.session(); saved['expires_at'] = 99999999999
        cloud._save(saved)
        with patch.object(cloud, '_request', side_effect=cloud.CloudError('connection_failed')):
            with self.assertRaises(cloud.CloudError):
                cloud.sign_out()
        self.assertIsNotNone(cloud.state())
        cloud.sign_out(local_only=True)
        self.assertIsNone(cloud.state())

    def test_endpoint_cannot_downgrade_or_embed_credentials(self):
        for value in ('http://xopilot.by', 'https://user:pass@xopilot.by', 'https://xopilot.by/path',
                      'https://xopilot.by?key=secret', 'file:///tmp/account'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cloud.normalize_endpoint(value)
        self.assertEqual(cloud.normalize_endpoint('http://127.0.0.1:7060/'),'http://127.0.0.1:7060')

    def test_redirect_never_receives_password_or_token(self):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(self.path)
                self.rfile.read(int(self.headers.get('Content-Length','0')))
                self.send_response(307)
                self.send_header('Location','/unexpected-destination')
                self.end_headers()
            def log_message(self, *_):
                pass
        server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with self.assertRaises(cloud.CloudError):
                cloud._request(f'http://127.0.0.1:{server.server_port}', '/auth/login',
                               method='POST', body={'password':'synthetic only'}, token='synthetic token')
            self.assertEqual(received, ['/api/v1/auth/login'])
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_registration_does_not_store_session_password_or_code(self):
        pending = {'registration_id':'synthetic', 'email':'qa@example.invalid'}
        with patch.object(cloud, '_request', return_value=pending) as request:
            self.assertEqual(cloud.begin_registration('Денис', 'qa@example.invalid',
                'Synthetic password 2026!', 'Synthetic password 2026!'), pending)
        self.assertIsNone(cloud.state())
        self.db.set_setting.assert_not_called()
        self.assertEqual(request.call_args.kwargs['body']['email'],'qa@example.invalid')
        self.assertNotIn('repeat_password',request.call_args.kwargs['body'])

    def test_registration_rejects_mismatched_password_and_bad_email_before_network(self):
        with patch.object(cloud, '_request') as request:
            for email, repeat in [('not mail', 'Synthetic password 2026!'),
                                  ('qa@example.invalid', 'different password')]:
                with self.subTest(email=email), self.assertRaises((ValueError, cloud.CloudError)):
                    cloud.begin_registration('Денис', email, 'Synthetic password 2026!', repeat)
            request.assert_not_called()

    def test_confirmation_rejects_incorrect_code_before_network(self):
        import uuid
        with patch.object(cloud, '_request') as request:
            with self.assertRaises(ValueError):
                cloud.confirm_registration(str(uuid.uuid4()), '123')
            request.assert_not_called()

    def test_verified_confirmation_persists_only_server_identity(self):
        import uuid
        tokens=dict(account_id='owner',session_id='device',access_token='token',refresh_token='refresh',expires_in=900)
        with patch.object(cloud, '_request', side_effect=[tokens, {'username':'Денис','display_name':'Денис','email':'qa@example.invalid'}]):
            self.assertEqual(cloud.confirm_registration(str(uuid.uuid4()), '123456')['email'],'qa@example.invalid')
        self.assertNotIn('123456',self.settings[cloud.KEY])

    def google_pending(self, **changes):
        import uuid
        identifier=str(uuid.uuid4())
        pending={'flow_id':identifier,'browser_url':f'https://xopilot.by/api/v1/auth/google/open/{identifier}?ticket='+ 'b'*64}
        return {**pending,**changes}

    def test_google_proof_stays_ephemeral_and_outside_browser_url(self):
        pending=self.google_pending()
        with patch('secrets.token_hex',return_value='a'*64), patch.object(cloud,'_request',return_value=pending) as request:
            result=cloud.begin_google()
        self.assertEqual(result['proof'],'a'*64)
        self.assertNotIn(result['proof'],result['browser_url'])
        self.assertNotIn('proof',request.call_args.kwargs['body'])
        self.assertNotEqual(request.call_args.kwargs['body']['proof_hash'],result['proof'])
        self.db.set_setting.assert_not_called()

    def test_google_rejects_foreign_browser_urls_before_launch(self):
        for url in ('https://attacker.invalid/login','http://xopilot.by/login','https://xopilot.by/other',
                    'https://user:pass@xopilot.by/login','javascript:alert(1)'):
            with self.subTest(url=url), patch.object(cloud,'_request',return_value=self.google_pending(browser_url=url)):
                with self.assertRaises(cloud.CloudError):cloud.begin_google()

    def test_google_login_persists_only_own_session(self):
        pending={**self.google_pending(),'proof':'a'*64,'endpoint':'https://xopilot.by','link':False}
        tokens={'account_id':'owner','session_id':'device','access_token':'token','refresh_token':'refresh','expires_in':900}
        with patch.object(cloud,'_request',side_effect=[{'status':'authenticated','tokens':tokens},
                {'username':'Google name','display_name':'Google name','email':'qa@example.invalid','google_linked':True}]):
            self.assertTrue(cloud.poll_google(pending))
        self.assertTrue(cloud.state()['google_linked'])
        self.assertNotIn(pending['proof'],self.settings[cloud.KEY])
        self.assertNotIn('access_token',cloud.state())

    def test_google_does_not_overwrite_another_login(self):
        cloud._save(self.session())
        with patch.object(cloud,'_request') as request:
            with self.assertRaises(ValueError):cloud.poll_google({'link':False})
            with self.assertRaises(cloud.CloudError):
                cloud.poll_google({'link':True,'account_id':'another','session_id':'device'})
            request.assert_not_called()

    def test_google_pending_and_failure_never_save_account(self):
        pending={**self.google_pending(),'proof':'a'*64,'endpoint':'https://xopilot.by','link':False}
        with patch.object(cloud,'_request',return_value={'status':'pending'}):self.assertFalse(cloud.poll_google(pending))
        with patch.object(cloud,'_request',return_value={'status':'failed','error':'google_account_exists'}):
            with self.assertRaises(cloud.CloudError):cloud.poll_google(pending)
        self.db.set_setting.assert_not_called()
