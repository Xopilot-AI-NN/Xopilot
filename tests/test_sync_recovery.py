"""Legacy conflict repair must preserve genuine local project edits."""
import copy
import json
import unittest
from unittest.mock import Mock

from App.services.cloud_sync import fingerprint
from App.services.sync_entities import Entities


class LegacyConflictRecoveryTests(unittest.TestCase):
    def test_known_local_deletion_rebases_newer_content_without_importing_it(self):
        key='chat:known'
        entities=object.__new__(Entities)
        record=dict(kind='chat',scope='chats',local_id=7,revision=1,hash='acknowledged')
        entities.ledger={'records':{key:record},'conflicts':{key:{}}}
        entities._local=Mock(return_value=None);entities.save=Mock();entities._apply=Mock()
        change=dict(kind='chat',id='known',revision=2,deleted=False,data={'scope':'chats'})
        entities.receive(key,change,{'title':'Newer remote version','messages':[]})
        self.assertEqual(record['revision'],2)
        self.assertEqual(record['hash'],'acknowledged')
        self.assertFalse(record.get('deleted',False),'The tombstone still needs server acknowledgment')
        self.assertFalse(record['blocked'])
        self.assertFalse(entities.ledger['conflicts'])
        entities._apply.assert_not_called()

    def test_concurrent_content_edits_remain_conflicts(self):
        key='chat:known'
        entities=object.__new__(Entities)
        record=dict(kind='chat',scope='chats',local_id=7,revision=1,hash='acknowledged')
        entities.ledger={'records':{key:record}};entities._local=Mock(return_value={'local':'edit'})
        entities.save=Mock();entities._apply=Mock()
        change=dict(kind='chat',id='known',revision=2,deleted=False,data={'scope':'chats'})
        entities.receive(key,change,{'remote':'edit'})
        self.assertTrue(record['blocked']);self.assertEqual(entities.ledger['conflicts'][key],change)
        entities._apply.assert_not_called()

    def test_first_pull_can_collapse_unknown_entity_to_its_deletion(self):
        for kind, scope in (('chat', 'chats'), ('workspace', 'workspaces'),
                            ('canvas', 'canvases'), ('chat', 'protected')):
            with self.subTest(scope=scope):
                key = kind + ':deleted-before-device-joined'
                entities = object.__new__(Entities)
                entities.ledger = {'records': {}, 'known_scopes': {key: scope}}
                entities.save = Mock()
                entities._apply = Mock(side_effect=AssertionError('No local entity to delete'))
                change = dict(kind=kind, id=key.split(':', 1)[1], revision=3,
                              deleted=True, data={})
                entities.receive(key, change, None)
                record = entities.ledger['records'][key]
                self.assertEqual(record['scope'], scope)
                self.assertEqual(record['revision'], 3)
                self.assertTrue(record['deleted'])
                self.assertEqual(record['hash'], 'deleted')
                self.assertIsNone(record['local_id'])
                entities._apply.assert_not_called()

    def test_changed_project_is_not_auto_replaced_after_chat_deletion(self):
        for field, value in (
            ('name', 'Changed name'),
            ('instructions', 'Keep this local instruction'),
            ('materials', [{'name': 'local note.md', 'path': '', 'type': 'Заметка'}]),
        ):
            with self.subTest(field=field):
                project = dict(id='project', name='Project', icon='CODE',
                               instructions='', materials=[])
                acknowledged = {k: project[k] for k in ('name', 'icon', 'instructions', 'materials')}
                acknowledged['chats'] = ['deleted-chat']
                project = copy.deepcopy(project)
                project[field] = value
                state = {'items': [project], 'chats': {'7': 'project'}}
                record = dict(scope='workspaces', local_id='project', blocked=True,
                              hash=fingerprint(acknowledged))
                entities = object.__new__(Entities)
                entities.options = {'workspaces': True}
                entities.db = Mock()
                entities.db.get_setting.return_value = json.dumps(state)
                entities.ledger = {'records': {
                    'workspace:project': record,
                    'chat:deleted-chat': dict(scope='chats', local_id=7, deleted=True),
                }, 'conflicts': {'workspace:project': {'deleted': False}}}
                entities.files = Mock()
                entities.save = Mock()
                entities.receive = Mock()
                entities.recover_deleted_chat_conflicts()
                entities.files.decode.assert_not_called()
                entities.receive.assert_not_called()
                self.assertTrue(record['blocked'])
                self.assertIn('workspace:project', entities.ledger['conflicts'])


if __name__ == '__main__':
    unittest.main()
