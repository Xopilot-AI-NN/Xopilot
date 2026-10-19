"""Portable snapshots and CAS imports. Credentials/settings are never exported."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid
from filelock import FileLock, Timeout
from .db import get_db
from .paths import app_data_dir
from .sync_crypto import canonical
from .cloud_sync import fingerprint, ledger_key


class Entities:
    def __init__(self,owner,options,ledger,files,save):
        self.owner,self.options,self.ledger,self.files,self.save=owner,options,ledger,files,save
        self.db=get_db()

    def _record(self,kind,identifier,scope,local_id=None):
        key=kind+':'+str(identifier)
        self.ledger['records'].setdefault(key,dict(kind=kind,scope=scope,local_id=local_id,revision=0,hash=None))
        return key

    def _chat_records(self):
        active={row[0] for row in self.db.list_chats()}
        bound={r.get('local_id') for r in self.ledger['records'].values() if r['scope']=='chats' and not r.get('deleted')}
        for cid in active-bound:
            raw=json.loads(self.db.sync_chat_snapshot(cid))
            if not raw['messages'] and raw['title']=='Новый чат': continue
            self._record('chat',uuid.uuid4(),'chats',cid)
        self.save()

    def _chat_map(self):
        return {r['local_id']:key.split(':',1)[1] for key,r in self.ledger['records'].items()
                if r['scope']=='chats' and not r.get('deleted') and r.get('local_id')}

    def _materials(self,items):
        result=[]
        for item in items:
            name,path=item if not isinstance(item,dict) else (item['name'],item.get('path',''))
            asset={'name':name,'missing':True}
            if self.options['materials'] and path:
                try:
                    cached=self.ledger.setdefault('assets',{}).get(str(path))
                    if cached and cached.get('excluded'):raise ValueError('Материал исключён из облачного хранилища')
                    stat=Path(path).stat() if Path(path).is_file() else None
                    stamp=[stat.st_size,stat.st_mtime_ns] if stat else None
                    if cached and (cached.get('stamp')==stamp or str(path) in json.loads(self.db.get_setting('material_removed_v1') or '{}')) and not cached.get('excluded'):
                        asset=copy.deepcopy(cached['manifest'])
                    else:
                        asset=self.files.upload_file(name,path)
                        self.ledger['assets'][str(path)]={'stamp':stamp,'manifest':copy.deepcopy(asset)}
                        self.save()
                except ValueError as exc:
                    if 'исключён' not in str(exc): raise
            # A shared file can have different library labels and switches.
            # Transport/cache names never replace the referring item's metadata.
            asset['name']=name.replace('\\','/')
            if isinstance(item,dict):
                asset['enabled']=item.get('enabled',True)
                if isinstance(item.get('type'),str):asset['type']=item['type']
            result.append(asset)
        return result

    def _restore_materials(self,assets):
        result=[]
        for item in assets:
            name=item['name'].replace('\\','/')
            filename=Path(name).name
            if item.get('missing'):path=''
            else:
                checksum=item['sha256']
                if len(checksum)!=64 or any(c not in '0123456789abcdef' for c in checksum):raise ValueError('Неверная контрольная сумма материала')
                path=str(app_data_dir()/'materials'/checksum/filename)
                trash=json.loads(self.db.get_setting('material_trash_v1') or '{}')
                trashed={str(app_data_dir()/'materials'/i['relative']) for i in trash.values()}
                if self.options['materials'] and path not in trashed and path not in json.loads(self.db.get_setting('material_removed_v1') or '{}') and not Path(path).is_file():
                    try:path=self.files.download_file(item)
                    except Exception as exc:
                        from .cloud_account import CloudError
                        if not isinstance(exc,CloudError) or exc.status!=404:raise
                stat=Path(path).stat() if Path(path).is_file() else None
                self.ledger.setdefault('assets',{})[path]={'manifest':copy.deepcopy(item),'stamp':[stat.st_size,stat.st_mtime_ns] if stat else None}
            result.append((name,path))
        return result

    def snapshots(self):
        from . import profile
        if self.options.get('profile',True) and profile.explicit(self.db):
            identifier=uuid.uuid5(uuid.UUID(self.owner),'Xopilot/profile/v1')
            key=self._record('profile',identifier,'profile','profile')
            data=profile.read(self.db)
            yield key,dict(deleted=False,hash=fingerprint(data),payload=data)
        self._chat_records()
        if self.options['chats']:
            for key,record in list(self.ledger['records'].items()):
                if record['scope']!='chats' or record.get('deleted'): continue
                raw=self.db.sync_chat_snapshot(record.get('local_id',0))
                if raw is None:
                    yield key,{'deleted':True,'hash':'deleted','payload':None};continue
                payload=json.loads(raw);digest=fingerprint(payload)
                if digest==record['hash'] and not record.get('force_upload'): continue
                for message in payload['messages']:
                    message['attachments']=self._materials(message['attachments'])
                yield key,dict(deleted=False,hash=digest,payload=payload)
        state=json.loads(self.db.get_setting('workspaces_v1') or '{"items":[],"chats":{},"selected":"all"}')
        chat_map=self._chat_map()
        if self.options['workspaces']:
            found=set()
            for item in state['items']:
                identifier=str(uuid.UUID(item['id']));key=self._record('workspace',identifier,'workspaces',item['id']);found.add(key)
                # Whitelist portable properties; local paths/settings do not travel.
                raw={k:item.get(k,'') for k in ('name','icon','instructions')}
                raw['materials']=item.get('materials',[])
                raw['chats']=[chat_map[int(cid)] for cid,wid in state['chats'].items() if wid==item['id'] and int(cid) in chat_map]
                raw['chats']=sorted(set(raw['chats'])|set(item.get('sync_pending_chat_uuids',[])));digest=fingerprint(raw)
                if digest==self.ledger['records'][key]['hash'] and not self.ledger['records'][key].get('force_upload'):continue
                payload=copy.deepcopy(raw);payload['materials']=self._materials(raw['materials'])
                yield key,dict(deleted=False,hash=digest,payload=payload)
            yield from self._missing('workspaces',found)
        if self.options['canvases']:
            found=set()
            for doc in json.loads(self.db.get_setting('canvases_v1') or '[]'):
                identifier=str(uuid.UUID(doc['id']));key=self._record('canvas',identifier,'canvases',doc['id']);found.add(key)
                payload=copy.deepcopy(doc);payload.pop('id',None);payload.pop('source_request',None)
                payload['chat_uuid']=chat_map.get(payload.pop('chat_id',None),doc.get('sync_chat_uuid'))
                payload.pop('sync_chat_uuid',None)
                yield key,dict(deleted=False,hash=fingerprint(doc),payload=payload)
            yield from self._missing('canvases',found)
        if self.options['protected']:
            root=app_data_dir()/'private-chats';found=set()
            for sealed in root.glob('*/chat.sealed'):
                try:
                    cid=-int(sealed.parent.name,16)
                    if not -(2**62)<=cid<0: continue
                except ValueError: continue
                existing=next((k for k,r in self.ledger['records'].items() if r['scope']=='protected' and r.get('local_id')==cid and not r.get('deleted')),None)
                was_deleted=any(r['scope']=='protected' and r.get('local_id')==cid and r.get('deleted') for r in self.ledger['records'].values())
                identifier=uuid.uuid4() if was_deleted else uuid.uuid5(uuid.UUID(self.owner),'private:'+str(cid))
                key=existing or self._record('chat',identifier,'protected',cid);found.add(key)
                lease=FileLock(str(sealed.parent/'session.lock'),thread_local=False)
                try: lease.acquire(timeout=0)
                except Timeout: continue  # Sync only complete, closed persistent vaults.
                try:
                    files=sorted(sealed.parent.glob('*.sealed'))
                    signatures=[(p.name,hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]
                    digest=fingerprint(signatures)
                    if digest==self.ledger['records'][key]['hash']: continue
                    payload={'cid':cid,'files':[self.files.upload_file(p.name,p) for p in files]}
                    yield key,dict(deleted=False,hash=digest,payload=payload)
                finally: lease.release()
            yield from self._missing('protected',found)
        self.save()

    def _missing(self,scope,found):
        for key,record in list(self.ledger['records'].items()):
            if record['scope']==scope and key not in found and not record.get('deleted'):
                yield key,dict(deleted=True,hash='deleted',payload=None)

    def _local(self,record):
        scope=record['scope'];local_id=record.get('local_id')
        if local_id is None and scope!='profile': return None
        if scope=='profile':
            from . import profile
            return profile.read(self.db) if profile.explicit(self.db) else None
        if scope=='chats':
            raw=self.db.sync_chat_snapshot(local_id or 0)
            return None if raw is None else json.loads(raw)
        if scope=='workspaces':
            state=json.loads(self.db.get_setting('workspaces_v1') or '{"items":[],"chats":{}}')
            item=next((i for i in state['items'] if i['id']==local_id),None)
            if not item:return None
            result={k:item.get(k,'') for k in ('name','icon','instructions')};result['materials']=item.get('materials',[])
            mapping=self._chat_map()
            result['chats']=sorted({mapping[int(cid)] for cid,wid in state['chats'].items() if wid==local_id and int(cid) in mapping}|set(item.get('sync_pending_chat_uuids',[])))
            return result
        if scope=='canvases':
            return next((i for i in json.loads(self.db.get_setting('canvases_v1') or '[]') if i['id']==local_id),None)
        path=app_data_dir()/'private-chats'/f'{abs(local_id):x}'
        files=sorted(path.glob('*.sealed'))
        return None if not (path/'chat.sealed').exists() else [(p.name,hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]

    def receive(self,key,change,payload):
        scope=(self.ledger['records'].get(key,{}).get('scope') or change['data'].get('scope')
               or self.ledger.get('known_scopes',{}).get(key))
        if scope not in ('profile','chats','workspaces','canvases','protected'):
            raise ValueError('Не удалось определить категорию облачного изменения')
        record=self.ledger['records'].setdefault(key,dict(kind=change['kind'],scope=scope,revision=0,hash=None,local_id=None))
        if change['deleted'] and record.get('local_id') is None:
            # A fresh device collapses create/update/delete history before
            # downloading. Tombstones contain no envelope or local entity.
            record.update(revision=change['revision'],hash='deleted',deleted=True)
            self.save();return
        current=self._local(record)
        if (scope=='chats' and not change['deleted'] and not record.get('deleted')
                and record.get('local_id') is not None and record.get('hash') is not None
                and current is None):
            # The known chat was deleted locally while this replica was offline.
            # Rebase its pending tombstone, not a content import into a missing
            # chat (which can also fail the messages' foreign-key constraint).
            record.update(revision=change['revision'],blocked=False)
            self.ledger.setdefault('conflicts',{}).pop(key,None)
            self.save();return
        if record.get('blocked') or (current is not None and fingerprint(current)!=record.get('hash')):
            self.ledger.setdefault('conflicts',{})[key]=change;record['blocked']=True;self.save();return
        if not self._apply(key,record,change,payload,current):
            self.ledger.setdefault('conflicts',{})[key]=change;record['blocked']=True;self.save()

    def _apply(self,key,record,change,payload,current):
        scope=record['scope'];revision=change['revision']
        old=copy.deepcopy(record)
        if scope=='profile':
            from . import profile
            if change['deleted']:raise ValueError('Удаление профиля не поддерживается')
            data=profile.validate(payload)
            expected=self.db.get_setting(profile.KEY);legacy=self.db.get_setting('profile_name')
            google_source=self.db.get_setting(profile.GOOGLE_SOURCE)
            fresh=profile.read(self.db) if profile.explicit(self.db) else None
            if fingerprint(fresh)!=fingerprint(current):return False
            record.update(local_id='profile',revision=revision,hash=fingerprint(data),deleted=False)
            if not self.db.apply_sync_settings([(profile.KEY,expected),('profile_name',legacy),(profile.GOOGLE_SOURCE,google_source)],
                [(profile.KEY,json.dumps(data,ensure_ascii=False)),('profile_name',data['name']),
                 (profile.GOOGLE_SOURCE,json.dumps(profile.manual_source(self.db),ensure_ascii=False)),
                 (ledger_key(self.owner),json.dumps(self.ledger,ensure_ascii=False))]):
                record.clear();record.update(old);return False
            return True
        if scope=='chats':
            raw=self.db.sync_chat_snapshot(record.get('local_id') or 0)
            if (None if raw is None else fingerprint(json.loads(raw))) != (None if current is None else fingerprint(current)):
                return False
            # Capture expected state before downloads; a concurrent edit is caught by SQL CAS.
            data=copy.deepcopy(payload)
            if data is not None:
                if not isinstance(data.get('messages'),list) or not isinstance(data.get('title'),str): raise ValueError('Неверные данные чата')
                for message in data['messages']: message['attachments']=self._restore_materials(message.get('attachments',[]))
            dependencies=[]
            if data is None:
                # Removing a cloud chat changes the derived project UUID list,
                # even when nobody edited that project locally. Rebase clean
                # project hashes in the same receipt transaction as the deletion.
                identifier=key.split(':',1)[1]
                projects=json.loads(self.db.get_setting('workspaces_v1') or '{"items":[],"chats":{}}')
                mapping=self._chat_map()
                remaining={cid:link for cid,link in mapping.items() if link!=identifier}
                for dependent in self.ledger['records'].values():
                    if dependent['scope']!='workspaces' or dependent.get('deleted') or dependent.get('blocked'):continue
                    if not any(item['id']==dependent.get('local_id') for item in projects['items']):continue
                    before=self._workspace_semantic(projects,dependent['local_id'],mapping)
                    if fingerprint(before)!=dependent.get('hash'):continue
                    after=self._workspace_semantic(projects,dependent['local_id'],remaining)
                    dependencies.append((dependent,dependent.get('hash')))
                    dependent['hash']=fingerprint(after)
            record.update(revision=revision,hash='deleted' if data is None else fingerprint(data),deleted=data is None)
            self.ledger['applying']=key
            actual=self.db.apply_sync_chat(record.get('local_id'),raw,None if data is None else json.dumps(data,ensure_ascii=False),ledger_key(self.owner),json.dumps(self.ledger,ensure_ascii=False))
            if actual is None:
                for dependent,digest in dependencies:dependent['hash']=digest
                record.clear();record.update(old);self.ledger.pop('applying',None);return False
            self.ledger.pop('applying',None);record['local_id']=actual
            self.save();return True
        if scope in ('workspaces','canvases'):
            setting='workspaces_v1' if scope=='workspaces' else 'canvases_v1'
            expected=self.db.get_setting(setting)
            state=json.loads(expected or ('{"items":[],"chats":{},"selected":"all"}' if scope=='workspaces' else '[]'))
            items=state['items'] if scope=='workspaces' else state
            if current is not None:
                fresh=self._workspace_semantic(state,record['local_id']) if scope=='workspaces' else next((i for i in items if i['id']==record['local_id']),None)
                if fingerprint(fresh)!=fingerprint(current):return False
            local_id=record.get('local_id') or uuid.UUID(key.split(':',1)[1]).hex
            items[:]=[item for item in items if item['id']!=local_id]
            if payload is not None:
                item=copy.deepcopy(payload);item['id']=local_id
                if scope=='workspaces':
                    assets=item.get('materials',[]);pairs=self._restore_materials(assets)
                    item['materials']=[dict(name=n,path=p,enabled=asset.get('enabled',True),
                        **({'type':asset['type']} if isinstance(asset.get('type'),str) else {})) for (n,p),asset in zip(pairs,assets)]
                    inverse={value:str(cid) for cid,value in self._chat_map().items()}
                    links=item.pop('chats',[]);item['sync_pending_chat_uuids']=[link for link in links if link not in inverse]
                    state['chats']={cid:wid for cid,wid in state['chats'].items() if wid!=local_id}
                    for identifier in links:
                        if identifier in inverse: state['chats'][inverse[identifier]]=local_id
                else:
                    item['sync_chat_uuid']=item.pop('chat_uuid',None)
                    inverse={value:cid for cid,value in self._chat_map().items()}
                    item['chat_id']=inverse.get(item['sync_chat_uuid'])
                items.append(item)
            elif scope=='workspaces':
                state['chats']={cid:wid for cid,wid in state['chats'].items() if wid!=local_id}
                if state.get('selected')==local_id:state['selected']='all'
            record.update(local_id=local_id,revision=revision,deleted=payload is None)
            # Imported paths/IDs belong to this device; hash its local representation.
            encoded=json.dumps(state,ensure_ascii=False)
            record['hash']='deleted' if payload is None else fingerprint(self._workspace_semantic(state,local_id) if scope=='workspaces' else item)
            updates=[(setting,encoded),(ledger_key(self.owner),json.dumps(self.ledger,ensure_ascii=False))]
            if not self.db.apply_sync_settings([(setting,expected)],updates):
                record.clear();record.update(old);return False
            return True
        return self._private_apply(key,record,change,payload)

    def _workspace_semantic(self,state,local_id,mapping=None):
        item=next(i for i in state['items'] if i['id']==local_id)
        result={k:item.get(k,'') for k in ('name','icon','instructions')};result['materials']=item.get('materials',[])
        if mapping is None:mapping=self._chat_map()
        result['chats']=sorted({mapping[int(cid)] for cid,wid in state['chats'].items() if wid==local_id and int(cid) in mapping}|set(item.get('sync_pending_chat_uuids',[])))
        return result

    def _private_apply(self,key,record,change,payload):
        cid=record.get('local_id') or (payload or {}).get('cid')
        if not isinstance(cid,int) or not -(2**62)<=cid<0:raise ValueError('Неверный защищённый чат')
        root=app_data_dir()/'private-chats';root.mkdir(parents=True,exist_ok=True,mode=0o700)
        folder=root/f'{abs(cid):x}';folder.mkdir(exist_ok=True,mode=0o700)
        lease=FileLock(str(folder/'session.lock'),thread_local=False)
        try:lease.acquire(timeout=0)
        except Timeout:return False
        try:
            actual=self._local({**record,'local_id':cid})
            if actual is not None and fingerprint(actual)!=record.get('hash'):return False
            if payload is None:
                # Preserve a local encrypted recovery copy before remote deletion.
                if (folder/'chat.sealed').exists():
                    self.backup_private_folder(folder,cid)
                    for file in folder.glob('*.sealed'):file.unlink()
                record.update(local_id=cid,revision=change['revision'],hash='deleted',deleted=True);self.save();return True
            names=[asset['name'] for asset in payload['files']]
            if 'chat.sealed' not in names or any(name!='chat.sealed' and (len(name)!=39 or not name.endswith('.sealed') or any(c not in '0123456789abcdef' for c in name[:32])) for name in names):
                raise ValueError('Неверные файлы защищённого чата')
            with tempfile.TemporaryDirectory(prefix='.sync-',dir=root) as temporary:
                stage=Path(temporary)
                for asset in payload['files']:self.files.download_file(asset,destination=stage/asset['name'])
                # Recovery image and staged copies survive failure; plaintext is never involved.
                if (folder/'chat.sealed').exists():self.backup_private_folder(folder,cid)
                for asset in payload['files']:
                    if asset['name']!='chat.sealed':os.replace(stage/asset['name'],folder/asset['name'])
                os.replace(stage/'chat.sealed',folder/'chat.sealed')
            signature=[(p.name,hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(folder.glob('*.sealed'))]
            record.update(local_id=cid,revision=change['revision'],hash=fingerprint(signature),deleted=False);self.save();return True
        finally:lease.release()

    def import_copy(self,scope,payload):
        kind={'chats':'chat','workspaces':'workspace','canvases':'canvas'}[scope]
        identifier=str(uuid.uuid4());key=self._record(kind,identifier,scope,None)
        copied=copy.deepcopy(payload)
        field='title' if scope!='workspaces' else 'name';copied[field]+=' · другая версия'
        change=dict(id=identifier,kind=kind,revision=0,deleted=False,data={'scope':scope})
        if not self._apply(key,self.ledger['records'][key],change,copied,None):
            raise RuntimeError('Не удалось сохранить другую версию')
        self.ledger['records'][key]['force_upload']=True
        self.save()

    def reconcile_links(self):
        mapping={value:cid for cid,value in self._chat_map().items()}
        expected=self.db.get_setting('workspaces_v1')
        if expected:
            state=json.loads(expected);changed=False
            for item in state['items']:
                remaining=[]
                for link in item.get('sync_pending_chat_uuids',[]):
                    if link in mapping:state['chats'][str(mapping[link])]=item['id'];changed=True
                    else:remaining.append(link)
                item['sync_pending_chat_uuids']=remaining
            if changed:self.db.apply_sync_settings([('workspaces_v1',expected)],[('workspaces_v1',json.dumps(state,ensure_ascii=False))])
        expected=self.db.get_setting('canvases_v1')
        if expected:
            docs=json.loads(expected);changed=False
            for doc in docs:
                link=doc.get('sync_chat_uuid')
                if doc.get('chat_id') is None and link in mapping:doc['chat_id']=mapping[link];changed=True
            if changed:self.db.apply_sync_settings([('canvases_v1',expected)],[('canvases_v1',json.dumps(docs,ensure_ascii=False))])

    def recover_deleted_chat_conflicts(self):
        if not self.options['workspaces']:return
        state=json.loads(self.db.get_setting('workspaces_v1') or '{"items":[],"chats":{}}')
        for key,change in list(self.ledger.get('conflicts',{}).items()):
            record=self.ledger['records'][key]
            if record['scope']!='workspaces' or record.get('deleted'):continue
            current=self._local(record)
            if current is None:continue
            deleted=[identifier.split(':',1)[1] for identifier,chat in self.ledger['records'].items()
                if chat['scope']=='chats' and chat.get('deleted')
                and state['chats'].get(str(chat.get('local_id')))==record.get('local_id')]
            if not deleted:continue
            before=copy.deepcopy(current);before['chats']=sorted(set(before['chats'])|set(deleted))
            # Reconstruct the exact acknowledged hash. If anything else was
            # edited, this proof fails and the user's conflict remains intact.
            if fingerprint(before)!=record.get('hash'):continue
            payload=None if change['deleted'] else self.files.decode(change['id'],change['data'])
            record.update(hash=fingerprint(current),blocked=False)
            self.receive(key,change,payload)
            if not record.get('blocked'):self.ledger['conflicts'].pop(key,None)
            self.save()

    def recover_local_chat_deletions(self):
        """Older/push-race conflicts must not permanently suppress a local deletion."""
        if not self.options['chats']:return
        for key,change in list(self.ledger.get('conflicts',{}).items()):
            record=self.ledger['records'][key]
            if (record['scope']!='chats' or record.get('deleted') or record.get('local_id') is None
                    or record.get('hash') is None or self._local(record) is not None):continue
            record['blocked']=False
            self.receive(key,change,None)
            if not record.get('blocked'):self.ledger['conflicts'].pop(key,None)
            self.save()


    def backup_private_folder(self,folder,cid):
        import time
        destination=app_data_dir()/'cloud-recovery'/self.owner/uuid.uuid4().hex
        destination.mkdir(parents=True,mode=0o700)
        for source in folder.glob('*.sealed'):shutil.copy2(source,destination/source.name)
        (destination/'metadata.json').write_text(json.dumps({'cid':cid,'time':time.time(),'label':'Защищённая версия'}))
        return destination

    def backup_private_payload(self,payload):
        import time
        cid=payload['cid'];names=[asset['name'] for asset in payload['files']]
        if not isinstance(cid,int) or not -(2**62)<=cid<0 or 'chat.sealed' not in names or any(n!='chat.sealed' and (len(n)!=39 or not n.endswith('.sealed') or any(c not in '0123456789abcdef' for c in n[:32])) for n in names):raise ValueError('Неверная защищённая версия')
        destination=app_data_dir()/'cloud-recovery'/self.owner/uuid.uuid4().hex
        destination.mkdir(parents=True,mode=0o700)
        for asset in payload['files']:self.files.download_file(asset,destination=destination/asset['name'])
        (destination/'metadata.json').write_text(json.dumps({'cid':cid,'time':time.time(),'label':'Версия защищённого чата из облака'}))
        return destination
