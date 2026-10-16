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
        p=patch.object(sync,'_auto_dirty',set());p.start();self.addCleanup(p.stop)

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

    def test_edit_during_inflight_sync_is_not_lost_until_idle_interval(self):
        def edit_during_pull():
            sync.request_soon()
            return {'sent':0,'received':0}
        with patch.object(sync.time,'monotonic',return_value=100),patch.object(sync,'run',side_effect=edit_during_pull):
            sync.run_auto_if_due()
        self.assertEqual(sync._auto_due['account-a'],105)
        self.assertNotIn('account-a',sync._auto_dirty)

    def test_local_edits_wake_idle_sync_without_bypassing_network_backoff(self):
        sync._auto_due['account-a']=200
        sync.request_soon();self.assertEqual(sync._auto_due['account-a'],0)
        sync._auto_due['account-a']=200;sync._auto_failures['account-a']=1
        sync.request_soon();self.assertEqual(sync._auto_due['account-a'],200)
        sync._auto_due['account-a']=float('inf');sync._auto_failures.clear()
        sync.request_soon();self.assertEqual(sync._auto_due['account-a'],float('inf'))


class SyncStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_idle_status_does_not_rescan_ledger_but_progress_updates(self):
        from unittest.mock import Mock
        from App.settings.account import sync as ui
        page=Mock();state={};ticks=0
        page.show_dialog.side_effect=lambda dialog:setattr(dialog,'open',True)
        async def tick(_):
            nonlocal ticks
            ticks+=1
            if ticks==2:state.update(running=True,phase='Получаем изменения')
            if ticks==4:page.show_dialog.call_args.args[0].open=False
        with patch.object(ui.sync,'options',return_value=dict(ui.sync.DEFAULTS)),\
             patch.object(ui.sync,'status',side_effect=lambda:dict(state)),\
             patch.object(ui.sync,'owner',return_value='qa'),\
             patch.object(ui.sync,'key_ready',return_value=True),\
             patch.object(ui.sync,'conflict_items',return_value={}) as scan,\
             patch.object(ui.cloud_traffic,'usage',return_value=0),\
             patch.object(ui.asyncio,'sleep',side_effect=tick):
            ui.open_sync(page)
            await page.run_task.call_args.args[0]()
            self.assertEqual(scan.call_count,2,'Scan once initially and once when progress changes')
            page.update.assert_called_once()
