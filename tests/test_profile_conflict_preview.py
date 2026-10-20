"""Authenticated previews must preserve both versions and reject stale choices."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch
from App.services import cloud_sync as sync,profile,sync_files,sync_entities
from App.services.sync_crypto import b64


class Settings:
    def __init__(self):self.data={}
    def get_setting(self,key):return self.data.get(key)
    def set_setting(self,key,value):self.data[key]=value
    def apply_sync_settings(self,expected,updates):
        if any(self.data.get(key)!=value for key,value in expected):return False
        self.data.update(updates);return True


class ProfilePreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.db=Settings();self.owner=str(uuid.uuid4())
        self.identifier=str(uuid.uuid4());self.record_key='profile:'+self.identifier
        self.secret=os.urandom(32)
        for module in (sync,profile,sync_entities):
            p=patch.object(module,'get_db',return_value=self.db);p.start();self.addCleanup(p.stop)
        for module in (sync,sync_files):
            p=patch.object(module,'app_data_dir',return_value=self.root);p.start();self.addCleanup(p.stop)
        p=patch.object(sync,'owner',return_value=self.owner);p.start();self.addCleanup(p.stop)
        self.local={'name':'Локальное имя','avatar':'','memory':{'enabled':True,'automatic':False,'items':[]}}
        self.cloud={'name':'Облачное имя','avatar':'','memory':{'enabled':False,'automatic':True,'items':[
            {'id':str(uuid.uuid4()),'text':'Изучаю Python','updated':123,'automatic':False}]}}
        self.db.set_setting(profile.KEY,json.dumps(self.local,ensure_ascii=False))
        self.db.set_setting('cloud_sync_key:'+self.owner,b64(self.secret))
        files=sync_files.Files(self.owner,self.secret,{},lambda:None)
        self.packet=files.encode(self.identifier,'profile',self.cloud)
        self.ledger={'records':{self.record_key:{'scope':'profile','kind':'profile','local_id':'profile','revision':1,'hash':'old','blocked':True}},
                     'conflicts':{self.record_key:{'id':self.identifier,'revision':2,'deleted':False,'data':self.packet}}}
        self.db.set_setting(sync.ledger_key(self.owner),json.dumps(self.ledger))

    def test_preview_authenticates_both_profiles_without_resolving_or_mutating_them(self):
        before=copy.deepcopy(self.db.data)
        result=sync.profile_conflict_preview(self.record_key)
        self.assertEqual(result['local'],self.local);self.assertEqual(result['cloud'],profile.validate(self.cloud))
        self.assertEqual(result['expected'],{'local':sync.fingerprint(self.local),'cloud':sync.fingerprint(profile.validate(self.cloud))})
        self.assertEqual(self.db.data,before)

    def test_change_after_preview_is_not_overwritten_and_no_recovery_is_written(self):
        expected=sync.profile_conflict_preview(self.record_key)['expected']
        updated={**self.local,'name':'Новое локальное имя'}
        self.db.set_setting(profile.KEY,json.dumps(updated));before=copy.deepcopy(self.db.data)
        for version in ('local','cloud'):
            with self.subTest(version=version),self.assertRaisesRegex(ValueError,'после просмотра'):
                sync.resolve_profile(self.record_key,version,expected=expected)
            self.assertEqual(self.db.data,before)

    def test_authenticated_remote_update_also_invalidates_the_previous_preview(self):
        expected=sync.profile_conflict_preview(self.record_key)['expected']
        files=sync_files.Files(self.owner,self.secret,{},lambda:None)
        self.ledger['conflicts'][self.record_key]['data']=files.encode(self.identifier,'profile',{**self.cloud,'name':'Новая облачная версия'})
        self.db.set_setting(sync.ledger_key(self.owner),json.dumps(self.ledger));before=copy.deepcopy(self.db.data)
        with self.assertRaisesRegex(ValueError,'после просмотра'):
            sync.resolve_profile(self.record_key,'cloud',expected=expected)
        self.assertEqual(self.db.data,before)

    def test_edit_between_preview_validation_and_import_is_preserved(self):
        expected=sync.profile_conflict_preview(self.record_key)['expected']
        original=sync_entities.Entities.__init__
        updated={**self.local,'name':'Изменение во время импорта'}
        def concurrently_edit(bridge,*args):
            original(bridge,*args)
            self.db.set_setting(profile.KEY,json.dumps(updated))
        with patch.object(sync_entities.Entities,'__init__',concurrently_edit):
            with self.assertRaisesRegex(ValueError,'Профиль изменился'):
                sync.resolve_profile(self.record_key,'cloud',expected=expected)
        self.assertEqual(profile.read(),updated)
        self.assertIn(self.record_key,sync.conflict_items())

    def test_tampered_envelope_cannot_be_shown_as_a_valid_choice(self):
        self.ledger['conflicts'][self.record_key]['data']['ciphertext']=b64(b'bad envelope')
        self.db.set_setting(sync.ledger_key(self.owner),json.dumps(self.ledger));before=copy.deepcopy(self.db.data)
        with self.assertRaises(ValueError):sync.profile_conflict_preview(self.record_key)
        self.assertEqual(self.db.data,before)
