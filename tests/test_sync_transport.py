"""Retry real transport semantics without duplicating encrypted operations."""
import unittest
from unittest.mock import patch

from App.services import cloud_account as cloud
from App.services.sync_files import Files


class TransportRetryTests(unittest.TestCase):
    def setUp(self):
        self.files = object.__new__(Files)
        self.files.owner = 'owner'
        self.options = dict(enabled=True, profile=True, chats=True,
                            workspaces=True, canvases=True, materials=True,
                            protected=False)
        self.files.expected_options = dict(self.options)
        for target, value in (
            ('App.services.cloud_account.state', {'account_id': 'owner'}),
            ('App.services.cloud_sync.options', self.options),
        ):
            mock = patch(target, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        sleeper = patch('App.services.sync_files.time.sleep')
        self.sleep = sleeper.start()
        self.addCleanup(sleeper.stop)

    def test_retry_preserves_operation_identity_and_encrypted_bytes(self):
        for payload in ({'method': 'PUT', 'raw': b'encrypted bytes'},
                        {'method': 'POST', 'body': {'operation_id': 'same-id'}}):
            with self.subTest(payload=payload), patch(
                'App.services.cloud_account.request',
                side_effect=[cloud.CloudError('connection_failed'), {'ok': True}],
            ) as request:
                self.assertEqual(self.files.request('/sync', **payload), {'ok': True})
                self.assertEqual(request.call_count, 2)
                self.assertEqual(request.call_args_list[0], request.call_args_list[1])
                self.assertEqual(request.call_args.kwargs, payload)

    def test_network_retries_are_bounded(self):
        with patch('App.services.cloud_account.request',
                   side_effect=cloud.CloudError('connection_failed')) as request:
            with self.assertRaises(cloud.CloudError):
                self.files.request('/files/id', method='PUT', raw=b'ciphertext')
            self.assertEqual(request.call_count, 3)
            self.assertEqual([call.args for call in self.sleep.call_args_list],
                             [(0.5,), (1.0,)])

    def test_non_network_and_budget_errors_are_not_retried(self):
        for error in (cloud.CloudError('quota_exceeded'), RuntimeError('Traffic budget')):
            with self.subTest(error=error), patch(
                'App.services.cloud_account.request', side_effect=error,
            ) as request:
                with self.assertRaises(type(error)):
                    self.files.request('/sync')
                request.assert_called_once()
                self.sleep.assert_not_called()

    def test_retry_rechecks_account_switch_disable_and_scope(self):
        for target, changed in (
            ('App.services.cloud_account.state', {'account_id': 'other'}),
            ('App.services.cloud_sync.options', dict(self.options, enabled=False)),
            ('App.services.cloud_sync.options', dict(self.options, materials=False)),
        ):
            with self.subTest(target=target, changed=changed):
                initial = {'account_id': 'owner'} if target.endswith('.state') else self.options
                with patch(target, side_effect=[initial, changed]), \
                     patch('App.services.cloud_account.request',
                           side_effect=cloud.CloudError('connection_failed')) as request:
                    with self.assertRaises(RuntimeError):
                        self.files.request('/sync')
                    request.assert_called_once()


if __name__ == '__main__':
    unittest.main()
