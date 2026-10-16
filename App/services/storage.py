"""Storage inventory and reversible removal of managed copies, never originals."""
import json
from pathlib import Path
import os
import time
import uuid
from filelock import FileLock
from .db import get_db
from .paths import app_data_dir, models_dir


def format_bytes(size):
    for unit in ('Б','КБ','МБ','ГБ'):
        if size<1024 or unit=='ГБ':return f'{size:.1f} {unit}' if unit!='Б' else f'{size} Б'
        size/=1024


def _size(root):
    if not root.exists():return 0
    return sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and not p.is_symlink())


def _managed(path):
    root=app_data_dir()/'materials';path=Path(path)
    relative=path.relative_to(root)
    if len(relative.parts)!=2 or len(relative.parts[0])!=64 or any(c not in '0123456789abcdef' for c in relative.parts[0]):
        raise ValueError('Можно управлять только копиями материалов Xopilot')
    if path.is_symlink() or path.parent.is_symlink() or root.is_symlink():raise ValueError('Ссылки не удаляются через хранилище')
    return path,relative


def material_references(db=None):
    """Include live references even when the cached file is currently missing."""
    db=db or get_db();references={}
    def add(path,label):references.setdefault(path,[]).append(label)
    for cid,title,_ in db.list_chats():
        for msg in db.get_messages(cid):
            for _,path in msg.attachments:add(path,'Чат: '+title)
        draft=json.loads(db.get_setting(f'draft:{cid}') or '{}')
        for path in draft.get('files',[]):add(path,'Черновик: '+title)
    projects=json.loads(db.get_setting('workspaces_v1') or '{"items":[]}')
    for item in projects['items']:
        for material in item.get('materials',[]):add(material.get('path',''),'Проект: '+item['name'])
    return references


def local_inventory():
    root=app_data_dir();db=get_db();references=material_references(db)
    files=[]
    for path in (root/'materials').glob('*/*'):
        try:_,relative=_managed(path)
        except ValueError:continue
        if path.is_file():files.append({'path':str(path),'name':path.name,'bytes':path.stat().st_size,'references':sorted(set(references.get(str(path),[])))})
    files.sort(key=lambda item:item['bytes'],reverse=True)
    allocated={}
    for item in files:
        stat=Path(item['path']).stat();allocated[(stat.st_dev,stat.st_ino)]=stat.st_size
    trash=json.loads(db.get_setting('material_trash_v1') or '{}')
    return {'db_bytes':sum((root/name).stat().st_size for name in ('xopilot.db','xopilot.db-wal','xopilot.db-shm') if (root/name).exists()),
            'materials_bytes':sum(allocated.values()),'private_bytes':_size(root/'private-chats'),
            'cache_bytes':_size(root/'cloud-cache'),'trash_bytes':_size(root/'material-trash'),
            'recovery_bytes':_size(root/'cloud-recovery'),'models_bytes':_size(models_dir()),'files':files,'trash':trash,'removed':json.loads(db.get_setting('material_removed_v1') or '{}')}


def trash_material(path):
    path,relative=_managed(path)
    root=app_data_dir()
    with FileLock(str(root/'material-storage.lock')):
        db=get_db();items=json.loads(db.get_setting('material_trash_v1') or '{}');identifier=uuid.uuid4().hex
        destination=root/'material-trash'/identifier;destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        items[identifier]={'relative':str(relative),'name':path.name,'bytes':path.stat().st_size,'time':time.time()}
        # Write receipt first; a failed move has an inert recoverable receipt.
        db.set_setting('material_trash_v1',json.dumps(items,ensure_ascii=False))
        os.replace(path,destination)
        return identifier


def restore_material(identifier):
    uuid.UUID(identifier)
    root=app_data_dir()
    with FileLock(str(root/'material-storage.lock')):
        db=get_db();items=json.loads(db.get_setting('material_trash_v1') or '{}');item=items[identifier]
        destination=root/'materials'/item['relative'];_managed(destination)
        if destination.exists():raise ValueError('Копия уже существует. Восстановление не заменяет существующие файлы')
        source=root/'material-trash'/identifier
        if not source.is_file() or source.is_symlink():raise ValueError('Файл корзины не найден')
        destination.parent.mkdir(parents=True,exist_ok=True)
        os.replace(source,destination)
        del items[identifier];db.set_setting('material_trash_v1',json.dumps(items,ensure_ascii=False))


def purge_material(identifier):
    """Permanently remove only the app-managed trash copy after UI confirmation."""
    uuid.UUID(identifier)
    root=app_data_dir()
    with FileLock(str(root/'material-storage.lock')):
        db=get_db();items=json.loads(db.get_setting('material_trash_v1') or '{}')
        if identifier not in items:raise ValueError('Файл корзины не найден')
        source=root/'material-trash'/identifier
        if source.is_symlink() or source.parent.is_symlink():raise ValueError('Ссылки не удаляются через хранилище')
        source.unlink(missing_ok=True)
        del items[identifier];db.set_setting('material_trash_v1',json.dumps(items,ensure_ascii=False))


def delete_local_material(path):
    """Free disk space without removing the original or the cloud copy."""
    path,relative=_managed(path)
    root=app_data_dir()
    with FileLock(str(root/'cloud-sync.lock'),thread_local=False,timeout=0),FileLock(str(root/'material-storage.lock')):
        removed=json.loads(get_db().get_setting('material_removed_v1') or '{}')
        removed[str(path)]={'name':path.name,'relative':str(relative),'time':time.time()}
        get_db().set_setting('material_removed_v1',json.dumps(removed,ensure_ascii=False))
        path.unlink(missing_ok=True)


def remove_unused_materials():
    """Remove only managed copies with no current chat, draft or project refs."""
    root=app_data_dir();count=0;freed=0
    with FileLock(str(root/'cloud-sync.lock'),thread_local=False,timeout=0),FileLock(str(root/'material-storage.lock')):
        inventory=local_inventory();db=get_db()
        removed=json.loads(db.get_setting('material_removed_v1') or '{}')
        for item in inventory['files']:
            if item['references']:continue
            path,relative=_managed(item['path']);stat=path.stat()
            removed[str(path)]={'name':path.name,'relative':str(relative),'time':time.time()}
            db.set_setting('material_removed_v1',json.dumps(removed,ensure_ascii=False))
            path.unlink();count+=1
            if stat.st_nlink==1:freed+=stat.st_size
    return {'count':count,'bytes':freed}

def restore_local_material(path):
    from . import cloud_sync as sync
    from .sync_crypto import unb64
    from .sync_files import Files
    path,_=_managed(path);identifier=sync.owner()
    with FileLock(str(app_data_dir()/'cloud-sync.lock'),thread_local=False,timeout=0):
        ledger=sync.read_ledger(identifier);asset=ledger.get('assets',{}).get(str(path))
        if not asset or asset.get('excluded') or asset['manifest'].get('missing'):raise ValueError('Облачной копии нет. Прикрепите исходный файл заново')
        key=get_db().get_setting('cloud_sync_key:'+identifier)
        if not key:raise ValueError('Введите пароль синхронизации')
        def save():get_db().set_setting(sync.ledger_key(identifier),json.dumps(ledger,ensure_ascii=False))
        from .cloud_traffic import metered
        with metered(identifier):Files(identifier,unb64(key),ledger,save).download_file(asset['manifest'],destination=path)
        stat=path.stat();asset['stamp']=[stat.st_size,stat.st_mtime_ns];save()
        removed=json.loads(get_db().get_setting('material_removed_v1') or '{}');removed.pop(str(path),None)
        get_db().set_setting('material_removed_v1',json.dumps(removed,ensure_ascii=False))


def cloud_inventory():
    from . import cloud_account as cloud, cloud_sync as sync, cloud_traffic
    identifier=sync.owner();files=[];cursor=''
    with cloud_traffic.metered(identifier):
        while True:
            reply=cloud.request('/storage'+('?after='+cursor if cursor else ''))
            files+=reply['files']
            if not reply['has_more']:break
            cursor=reply['next']
    reply['files']=files
    ledger=sync.read_ledger(identifier)
    by_id={row['id']:row for row in files};groups=[];claimed=set();grouped={}
    for path,asset in ledger.get('assets',{}).items():
        parts=asset['manifest'].get('chunks',[]);available=[p for p in parts if p in by_id]
        if available and not asset.get('excluded'):
            identity=tuple(parts)
            if identity in grouped:
                grouped[identity]['aliases'].append(asset['manifest']['name'])
                continue
            item={'name':asset['manifest']['name'],'path':path,'ids':available,
                'bytes':sum(by_id[p]['bytes'] for p in set(available)),
                'source_bytes':asset['manifest'].get('size',0),'complete':len(available)==len(parts),
                'aliases':[asset['manifest']['name']]}
            groups.append(item);grouped[identity]=item
            claimed.update(available)
    reply['excluded_materials']=[{'path':path,'name':asset['manifest']['name']} for path,asset in ledger.get('assets',{}).items() if asset.get('excluded') and Path(path).is_file()]
    # A block can be shared by multiple files. The quota breakdown must count
    # physical cloud blocks once, even when several manifests refer to them.
    reply['materials']=groups
    reply['material_bytes']=sum(by_id[key]['bytes'] for key in claimed)
    payloads=[row for row in files if row['id'] not in claimed and row.get('sync_payload')]
    unknown=[row for row in files if row['id'] not in claimed and not row.get('sync_payload')]
    reply['sync_payload_bytes']=sum(row['bytes'] for row in payloads)
    reply['unmapped_files']=unknown
    reply['unmapped_bytes']=sum(row['bytes'] for row in unknown)
    reply['other_file_bytes']=reply['sync_payload_bytes']+reply['unmapped_bytes']
    return reply


def recover_cloud_materials():
    """Recover file descriptions, never transcripts or file bodies, from E2EE history."""
    from . import cloud_sync as sync,cloud_traffic
    from .sync_files import Files
    from .sync_crypto import unb64
    identifier=sync.owner();opts=sync.options(identifier)
    if not opts['enabled'] or not opts['materials']:
        raise ValueError('Включите синхронизацию материалов, чтобы прочитать их зашифрованные описания')
    key=get_db().get_setting('cloud_sync_key:'+identifier)
    if not key:raise ValueError('Введите пароль синхронизации')
    root=app_data_dir();root.mkdir(parents=True,exist_ok=True)
    with FileLock(str(root/'cloud-sync.lock'),thread_local=False,timeout=0):
        ledger=sync.read_ledger(identifier)
        scopes=[scope for scope in ('chats','workspaces') if opts.get(scope)]
        cursor=ledger.get('storage_catalog_cursor',0) if ledger.get('storage_catalog_scopes')==scopes else 0
        files=Files(identifier,unb64(key),ledger,lambda:None)
        files.expected_options=opts
        latest={};found=0
        with cloud_traffic.metered(identifier):
            while True:
                reply=files.request(f'/sync/pull?after={cursor}&limit=100')
                for change in reply['changes']:
                    scope=change['data'].get('scope')
                    # No private vaults, profiles or Canvas are opened by this action.
                    if not change['deleted'] and scope in ('chats','workspaces') and opts.get(scope):
                        latest[(change['id'],json.dumps(change['data'],sort_keys=True))]=change
                cursor=reply['cursor']
                if not reply['has_more']:break
            for change in latest.values():
                try:payload=files.decode(change['id'],change['data'])
                except Exception as exc:
                    from .cloud_account import CloudError
                    if isinstance(exc,CloudError) and exc.status==404:continue
                    raise
                manifests=list(payload.get('materials',[]))
                for message in payload.get('messages',[]):manifests.extend(message.get('attachments',[]))
                for manifest in manifests:
                    if not isinstance(manifest,dict) or manifest.get('missing'):continue
                    name=manifest.get('name','');checksum=manifest.get('sha256','');parts=manifest.get('chunks')
                    size=manifest.get('size')
                    if not isinstance(name,str) or not isinstance(checksum,str) or len(checksum)!=64 or any(c not in '0123456789abcdef' for c in checksum):continue
                    if not isinstance(size,int) or not 0<=size<=512*1024*1024 or not isinstance(parts,list) or len(parts)>128:continue
                    try:parts=[str(uuid.UUID(part)) for part in parts]
                    except (ValueError,TypeError,AttributeError):continue
                    if set(parts)&set(ledger.get('excluded_blobs',[])):continue
                    filename=Path(name.replace('\\','/')).name
                    if filename in ('','.','..'):continue
                    path=str(root/'materials'/checksum/filename)
                    if path not in ledger.setdefault('assets',{}):
                        ledger['assets'][path]={'manifest':{**manifest,'chunks':parts},'stamp':None,'recovered':True}
                        found+=1
            # Existing choices are never overridden. Only descriptions are added
            # under the replication lease; the sync cursor itself is untouched.
            if sync.owner()!=identifier or any(sync.options(identifier)[scope]!=opts[scope] for scope in ('enabled','materials','chats','workspaces')):
                raise ValueError('Аккаунт или выбор данных изменился. Повторите поиск')
            ledger['storage_catalog_scopes']=scopes
            ledger['storage_catalog_cursor']=cursor
            get_db().set_setting(sync.ledger_key(identifier),json.dumps(ledger,ensure_ascii=False))
        return {'found':found,'cursor':cursor}


def remove_cloud_material(path):
    from . import cloud_account as cloud, cloud_sync as sync, cloud_traffic
    identifier=sync.owner()
    lease=FileLock(str(app_data_dir()/'cloud-sync.lock'),thread_local=False,timeout=0)
    with lease:
        ledger=sync.read_ledger(identifier);asset=ledger['assets'][path]
        parts=asset['manifest'].get('chunks',[])
        # Exclusion is durable even if a deletion is interrupted; retry is safe.
        for entry in ledger['assets'].values():
            if set(entry['manifest'].get('chunks',[])) & set(parts):entry['excluded']=True
        ledger['excluded_blobs']=sorted(set(ledger.get('excluded_blobs',[]))|set(parts))
        for record in ledger['records'].values():
            if record['scope'] in ('chats','workspaces'):record['force_upload']=True
        get_db().set_setting(sync.ledger_key(identifier),json.dumps(ledger,ensure_ascii=False))
        with cloud_traffic.metered(identifier):
            for part in parts:cloud.request('/files/'+part,method='DELETE')
        # Local originals/copies and transcripts are retained.


def include_cloud_material(path):
    from . import cloud_sync as sync
    identifier=sync.owner()
    with FileLock(str(app_data_dir()/'cloud-sync.lock'),thread_local=False,timeout=0):
        ledger=sync.read_ledger(identifier)
        entry=ledger['assets'][path];entry['excluded']=False
        # Deleted blob UUIDs have server tombstones. A new per-material generation
        # is needed rather than silently reusing a deleted storage identity.
        entry['stamp']=None
        for part in entry['manifest'].get('chunks',[]):
            digest=ledger.get('blobs',{}).get(part,{}).get('digest')
            if digest:ledger.setdefault('blob_generations',{})[digest]=ledger.get('blob_generations',{}).get(digest,0)+1
        for record in ledger['records'].values():
            if record['scope'] in ('chats','workspaces'):record['force_upload']=True
        get_db().set_setting(sync.ledger_key(identifier),json.dumps(ledger,ensure_ascii=False))



def private_recoveries():
    result=[]
    for metadata in (app_data_dir()/'cloud-recovery').glob('*/*/metadata.json'):
        if metadata.is_symlink():continue
        try:
            item=json.loads(metadata.read_text());item['path']=str(metadata.parent)
            result.append(item)
        except (ValueError,OSError):continue
    return sorted(result,key=lambda i:i.get('time',0),reverse=True)


def restore_private_recovery(path):
    from .private_chats import _atomic
    root=app_data_dir()/'cloud-recovery';source=Path(path)
    relative=source.relative_to(root)
    if len(relative.parts)!=2 or source.is_symlink() or source.parent.is_symlink() or root.is_symlink():raise ValueError('Неверная копия восстановления')
    for component in relative.parts:uuid.UUID(component)
    item=json.loads((source/'metadata.json').read_text());cid=item['cid']
    if not isinstance(cid,int) or not -(2**62)<=cid<0:raise ValueError('Неверный защищённый чат')
    folder=app_data_dir()/'private-chats'/f'{abs(cid):x}';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    lease=FileLock(str(folder/'session.lock'),thread_local=False)
    try:lease.acquire(timeout=0)
    except Exception:raise ValueError('Сначала закройте защищённый чат') from None
    try:
        if (folder/'chat.sealed').exists():
            import shutil
            backup=root/relative.parts[0]/uuid.uuid4().hex
            backup.mkdir(parents=True,mode=0o700)
            for sealed in folder.glob('*.sealed'):shutil.copy2(sealed,backup/sealed.name)
            (backup/'metadata.json').write_text(json.dumps({'cid':cid,'time':time.time(),'label':'Версия до восстановления'}))
        names=[p.name for p in source.glob('*.sealed')]
        if any((source/name).is_symlink() for name in names):raise ValueError('Ссылки не восстанавливаются')
        if 'chat.sealed' not in names:raise ValueError('Неполная копия')
        for name in names:
            if name!='chat.sealed' and (len(name)!=39 or any(c not in '0123456789abcdef' for c in name[:32]) or not name.endswith('.sealed')):raise ValueError('Неверные файлы копии')
            if name!='chat.sealed':_atomic(folder/name,(source/name).read_bytes())
        _atomic(folder/'chat.sealed',(source/'chat.sealed').read_bytes())
    finally:lease.release()
