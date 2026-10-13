"""Owner OAuth setup boundaries, with synthetic provider responses only."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit
from scripts import connect_donationalerts as setup


class OwnerOAuthTests(unittest.TestCase):
    def test_request_and_callback_require_exact_state_and_one_code(self):
        url=setup.authorization_url('123',setup.REDIRECT,'test-state')
        query=parse_qs(urlsplit(url).query)
        self.assertEqual(query['scope'],[setup.SCOPES])
        self.assertEqual(query['redirect_uri'],[setup.REDIRECT])
        self.assertEqual(setup.callback_code('/callback?state=test-state&code=one-use','/callback','test-state'),'one-use')
        for target in ('/callback?state=wrong&code=one-use', '/other?state=test-state&code=one-use',
                       '/callback?state=test-state&code=first&code=second', '/callback?state=test-state&error=denied',
                       '/callback?code=one-use', '/callback?state=test-state&state=test-state&code=one-use'):
            with self.subTest(target=target),self.assertRaises(ValueError):setup.callback_code(target,'/callback','test-state')

    def test_exchange_verifies_recipient_and_donation_scope_before_saving(self):
        def response(data):return io.BytesIO(json.dumps(data).encode())
        opener=Mock()
        opener.open.side_effect=[response({'access_token':'synthetic-access','refresh_token':'synthetic-refresh','expires_in':631151999}),
            response({'data':{'code':'denbroliik'}}),response({'data':[]})]
        tokens=setup.exchange('123','synthetic-client-secret',setup.REDIRECT,'synthetic-code','denbroliik',opener)
        self.assertEqual(tokens['access_token'],'synthetic-access')
        calls=opener.open.call_args_list
        self.assertEqual(len(calls),3)
        body=parse_qs(calls[0].args[0].data.decode())
        self.assertEqual(body['client_secret'],['synthetic-client-secret'])
        self.assertTrue(calls[2].args[0].full_url.endswith('/alerts/donations?page=1'))
        opener.open.side_effect=[response({'access_token':'synthetic-access','refresh_token':'synthetic-refresh','expires_in':3600}),
            response({'data':{'code':'other-owner'}})]
        with self.assertRaisesRegex(ValueError,'другой получатель'):
            setup.exchange('123','synthetic-secret',setup.REDIRECT,'synthetic-code','denbroliik',opener)

    def test_token_file_is_private_and_cannot_replace_an_existing_file_or_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);target=root/'tokens.json'
            tokens={'access_token':'synthetic-access','refresh_token':'synthetic-refresh','expires_at':100}
            setup.write_tokens(target,tokens)
            self.assertEqual(json.loads(target.read_text()),tokens)
            if os.name=='posix':self.assertEqual(target.stat().st_mode & 0o777,0o600)
            with self.assertRaises(FileExistsError):setup.write_tokens(target,{'access_token':'replacement'})
            link=root/'link';link.symlink_to(target)
            with self.assertRaises(FileExistsError):setup.write_tokens(link,tokens)
            root.chmod(0o755)
            if os.name=='posix':
                with self.assertRaisesRegex(ValueError,'700'):setup.write_tokens(root/'unsafe.json',tokens)
