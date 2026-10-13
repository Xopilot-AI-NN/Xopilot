import base64
import io
import unittest
from unittest.mock import AsyncMock,Mock,patch
from types import SimpleNamespace
import flet as ft
from PIL import Image
from App.services import profile,billing

class ProfileTests(unittest.TestCase):
    def database(self):
        values={};db=Mock();db.get_setting.side_effect=values.get
        def cas(expected,updates):
            if any(values.get(k)!=v for k,v in expected):return False
            values.update(updates);return True
        db.apply_sync_settings.side_effect=cas
        return db,values
    def avatar(self,color):
        image=io.BytesIO();Image.new('RGB',(256,256),color).save(image,'JPEG')
        return profile.normalize_avatar(image.getvalue())
    def test_google_seeds_blank_profile_and_preserves_manual_fields(self):
        db,values=self.database();a=self.avatar('red');b=self.avatar('blue')
        profile.import_google('owner',name='Google name',avatar=a,picture_url='https://lh3.googleusercontent.com/a',db=db)
        self.assertEqual(profile.read(db),{'name':'Google name','avatar':a})
        self.assertFalse(profile.needs_google_avatar('https://lh3.googleusercontent.com/a',db))
        with patch.object(profile,'get_db',return_value=db):profile.update(name='My custom name')
        profile.import_google('owner',name='Changed Google name',avatar=b,picture_url='https://lh3.googleusercontent.com/b',db=db)
        self.assertEqual(profile.read(db),{'name':'My custom name','avatar':b})
        with patch.object(profile,'get_db',return_value=db):profile.update(avatar=a)
        self.assertFalse(profile.needs_google_avatar('https://lh3.googleusercontent.com/c',db))
        profile.import_google('owner',name='Another Google name',avatar=None,db=db)
        self.assertEqual(profile.read(db),{'name':'My custom name','avatar':a})
    def test_google_does_not_replace_existing_local_or_synced_profile(self):
        db,values=self.database();a=self.avatar('green')
        with patch.object(profile,'get_db',return_value=db):profile.update(name='Existing profile',avatar=a)
        profile.import_google('owner',name='Google name',avatar=self.avatar('blue'),db=db)
        self.assertEqual(profile.read(db),{'name':'Existing profile','avatar':a})
    def test_explicit_default_name_and_removed_avatar_are_preserved(self):
        db,values=self.database();a=self.avatar('red')
        profile.import_google('owner',name='Google name',avatar=a,db=db)
        with patch.object(profile,'get_db',return_value=db):profile.update(name='Пользователь',avatar='')
        profile.import_google('owner',name='Changed Google name',avatar=a,db=db)
        self.assertEqual(profile.read(db),{'name':'Пользователь','avatar':''})
        self.assertFalse(profile.needs_google_avatar('https://lh3.googleusercontent.com/a',db))
    def test_concurrent_name_edit_wins_over_google_import(self):
        db,values=self.database();cas=db.apply_sync_settings.side_effect;first=True
        def race(expected,updates):
            nonlocal first
            if first:
                first=False;values['profile_name']='Concurrent custom name';return False
            return cas(expected,updates)
        db.apply_sync_settings.side_effect=race
        profile.import_google('owner',name='Google name',avatar=self.avatar('blue'),db=db)
        self.assertEqual(profile.read(db)['name'],'Concurrent custom name')
    def test_avatar_is_bounded_reencoded_and_metadata_removed(self):
        source=io.BytesIO();Image.new('RGB',(640,480),'#00c9ac').save(source,'PNG')
        avatar=profile.normalize_avatar(source.getvalue())
        with Image.open(io.BytesIO(base64.b64decode(avatar))) as image:
            self.assertEqual(image.size,(256,256));self.assertEqual(image.format,'JPEG');self.assertFalse(image.getexif())
        self.assertEqual(profile.validate({'name':' Денис ','avatar':avatar})['name'],'Денис')
        for data in ({'name':'','avatar':''},{'name':'name','avatar':'broken'},{'name':'a'*51,'avatar':''}):
            with self.assertRaises(ValueError):profile.validate(data)
    def test_monthly_catalog_and_discounts_require_verification(self):
        self.assertEqual([row['name'] for row in billing.PLANS],['Zephyr Micro','Zephyr Elite','Zephyr Ultra','Zephyr Led'])
        self.assertEqual([row['rub'] for row in billing.PLANS],[0,1000,4000,7000])
        self.assertTrue(all(row['period']=='month' for row in billing.PLANS))
        self.assertEqual(billing.elite_price('institution'),1000)
        self.assertEqual(billing.elite_price('institution',verified=True),600)
        self.assertEqual(billing.elite_price('programmer',verified=True),800)


class AndroidAvatarTests(unittest.IsolatedAsyncioTestCase):
    async def test_android_avatar_uses_restart_safe_native_picker(self):
        from App.settings.account import main as account
        page=Mock(width=400,web=False)
        picker=Mock()
        with patch('App.services.platforms.is_android',return_value=True), \
             patch.object(account.ft,'FilePicker',return_value=picker), \
             patch.object(account,'get_stats',return_value=dict(messages=0,tokens=0,app_seconds=0)), \
             patch.object(account,'build_cloud_card',return_value=ft.Container()), \
             patch.object(profile,'read',return_value={'name':'Profile','avatar':''}), \
             patch('App.services.mobile_documents.pick_avatar',AsyncMock(return_value={'profile':True})) as select:
            content=account.build_account_page(page)
            avatar=content.controls[0].content.controls[0]
            await avatar.on_click(None)
            select.assert_awaited_once_with()
            picker.pick_files.assert_not_called()
            self.assertEqual(avatar.width,56)
