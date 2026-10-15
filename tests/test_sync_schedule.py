"""
Файл: /tests/test_sync_schedule.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Проверки периодов синхронизации, сетевых сбоев и изоляции аккаунтов.
"""
import unittest
from unittest.mock import patch
from App.services import cloud_sync as sync


class SyncScheduleTests(unittest.TestCase):
    def setUp(self):
        for name,value in [('owner','account-a'),('options',{'enabled':True,'auto':True})]:
            p=patch.object(sync,name,return_value=value);p.start();self.addCleanup(p.stop)
        for name in ('_auto_due','_auto_failures','_status'):
            p=patch.dict(getattr(sync,name),{},clear=True);p.start();self.addCleanup(p.stop)

    def test_activity_is_fast_and_idle_avoids_unnecessary_traffic(self):
        with patch.object(sync.time,'monotonic',return_value=100),patch.object(sync,'run',return_value={'sent':1}) as run:
            sync.run_auto_if_due();self.assertEqual(sync._auto_due['account-a'],115)
            self.assertIsNone(sync.run_auto_if_due());run.assert_called_once()
        with patch.object(sync.time,'monotonic',return_value=115),patch.object(sync,'run',return_value={}):
            sync.run_auto_if_due();self.assertEqual(sync._auto_due['account-a'],175)

    def test_network_failure_backoff_and_successful_recovery(self):
        for now,delay in [(100,15),(115,30),(145,60),(205,120),(325,240),(565,300)]:
            with patch.object(sync.time,'monotonic',return_value=now),patch.object(sync,'run',side_effect=OSError('offline')):
                with self.assertRaises(OSError):sync.run_auto_if_due()
                self.assertEqual(sync._auto_due['account-a'],now+delay)
                self.assertIsNotNone(sync._status['account-a']['next_retry'])
        with patch.object(sync.time,'monotonic',return_value=865),patch.object(sync,'run',return_value={'received':1}):
            sync.run_auto_if_due();self.assertNotIn('account-a',sync._auto_failures)
            self.assertIsNone(sync._status['account-a']['next_retry'])

    def test_busy_lease_and_other_accounts_do_not_wait_a_minute(self):
        with patch.object(sync.time,'monotonic',return_value=100),patch.object(sync,'run',return_value={'busy':True}) as run:
            sync.run_auto_if_due();self.assertEqual(sync._auto_due['account-a'],105)
            with patch.object(sync,'owner',return_value='account-b'):sync.run_auto_if_due()
            self.assertEqual(run.call_count,2)

    def test_disabled_auto_never_uses_network(self):
        with patch.object(sync,'options',return_value={'enabled':True,'auto':False}),patch.object(sync,'run') as run:
            self.assertIsNone(sync.run_auto_if_due());run.assert_not_called()

    def test_local_edits_wake_idle_sync_without_bypassing_network_backoff(self):
        sync._auto_due['account-a']=200
        sync.request_soon();self.assertEqual(sync._auto_due['account-a'],0)
        sync._auto_due['account-a']=200;sync._auto_failures['account-a']=1
        sync.request_soon();self.assertEqual(sync._auto_due['account-a'],200)
        sync._auto_due['account-a']=float('inf');sync._auto_failures.clear()
        sync.request_soon();self.assertEqual(sync._auto_due['account-a'],float('inf'))
