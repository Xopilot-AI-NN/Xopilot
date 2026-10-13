import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from App.services import storage, billing, cloud_traffic as traffic

class Settings:
    def __init__(self):self.items={}
    def get_setting(self,key):return self.items.get(key)
    def set_setting(self,key,value):self.items[key]=value

class CloudStorageBilling(unittest.TestCase):
    def test_rolling_budget_owner_isolation_and_failed_attempts(self):
        db=Settings();db.set_setting('cloud_sync_options:a',json.dumps({'traffic_limit':True,'daily_limit_bytes':10}))
        with patch.object(traffic,'get_db',return_value=db),patch.object(traffic.time,'time',return_value=100000):
            db.set_setting(traffic.key('a'),json.dumps([[1,100]]))
            with traffic.metered('a'):
                traffic.reserve(6)
                with self.assertRaises(RuntimeError):traffic.reserve(5)
                self.assertEqual(traffic.usage('a'),6)
            with traffic.metered('b'):traffic.reserve(50)
            self.assertEqual(traffic.usage('b'),50)
            with patch.object(traffic.time,'time',return_value=200000):self.assertEqual(traffic.usage('a'),0)
    def test_trash_restore_and_permanent_delete_only_managed_copy(self):
        db=Settings()
        with tempfile.TemporaryDirectory() as directory,patch.object(storage,'get_db',return_value=db),patch.object(storage,'app_data_dir',return_value=Path(directory)):
            root=Path(directory);original=root/'original.txt';original.write_text('original')
            managed=root/'materials'/('a'*64)/'copy.txt';managed.parent.mkdir(parents=True);managed.write_text('copy')
            with self.assertRaises(ValueError):storage.trash_material(original)
            identifier=storage.trash_material(managed);self.assertFalse(managed.exists());self.assertTrue(original.exists())
            storage.restore_material(identifier);self.assertEqual(managed.read_text(),'copy')
            identifier=storage.trash_material(managed);storage.purge_material(identifier)
            self.assertFalse((root/'material-trash'/identifier).exists());self.assertTrue(original.exists())
            managed.symlink_to(original)
            with self.assertRaises(ValueError):storage.trash_material(managed)
    def test_currency_region_override_and_decimal_prices(self):
        db=Settings()
        with patch.object(billing,'get_db',return_value=db),patch.object(billing.locale,'getlocale',return_value=('ru_BY','UTF-8')):
            self.assertEqual(billing.currency(),'BYN')
            billing.set_currency('EUR');self.assertEqual(billing.currency(),'EUR')
            with patch.object(billing,'rates',return_value={'date':'04.10.2026','values':{'EUR':'100'}}):
                value=billing.prices();self.assertEqual(value['plans'][1]['label'],'≈ 10.00 EUR');self.assertFalse(value['plans'][1]['available'])
            with patch.object(billing,'rates',return_value={}):self.assertEqual(billing.prices()['plans'][1]['label'],'1 000 RUB')

    def test_corrupted_exchange_rate_cache_does_not_break_plan_list(self):
        db=Settings()
        with patch.object(billing,'get_db',return_value=db),patch.object(billing.urllib.request,'urlopen',side_effect=OSError('offline')):
            for raw in ('invalid-json','[]','{"values":{"EUR":"NaN"},"fetched_at":1}',
                        '{"values":{"EUR":"-1"},"fetched_at":1}', '{"values":{},"fetched_at":"invalid"}'):
                db.set_setting('cbr_display_rates_v1',raw)
                with self.subTest(raw=raw):self.assertEqual(billing.rates(),{})
