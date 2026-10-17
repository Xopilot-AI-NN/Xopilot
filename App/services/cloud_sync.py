"""
Файл: /App/services/cloud_sync.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Сквозная синхронизация, восстановление передачи и адаптивные повторы.
"""
import copy
import hashlib
import json
import threading
import time
import uuid
from pathlib import Path
from filelock import FileLock, Timeout
from . import cloud_account as cloud, cloud_traffic
from .db import get_db
from .paths import app_data_dir
from .sync_crypto import make_keyring, unlock_keyring, b64, unb64, canonical
from .sync_files import Files

DEFAULTS=dict(profile=True,enabled=False, auto=False, chats=True, workspaces=True, canvases=True,
              materials=True, protected=False, traffic_limit=False, daily_limit_bytes=10*1024*1024)
_lock=threading.RLock()
_status={}


def owner():
    account=cloud.state()
    if not account: raise ValueError('Сначала войдите в облачный аккаунт')
    return account['account_id']


def settings_key(identifier): return 'cloud_sync_options:'+identifier


def options(identifier=None):
    identifier=identifier or owner()
    return {**DEFAULTS, **json.loads(get_db().get_setting(settings_key(identifier)) or '{}')}


def save_options(value):
    identifier=owner();previous=options(identifier);updated={**previous,**value}
    if not isinstance(updated['daily_limit_bytes'],int) or not 1024<=updated['daily_limit_bytes']<=1024**4:
        raise ValueError('Введите лимит от 1 КБ до 1 ТБ')
    if updated['enabled'] and not get_db().get_setting('cloud_sync_key:'+identifier):
        raise ValueError('Сначала задайте пароль синхронизации')
    if updated['materials'] and not previous['materials']:
        # Fingerprints describe local content, not the previous upload policy.
        # Unchanged chats/projects must publish their files after opt-in.
        # Apply this under run's lease, never race a cursor/pending write.
        updated['materials_generation']=previous.get('materials_generation',0)+1
    get_db().set_setting(settings_key(identifier),json.dumps(updated))
    with _lock:
        _auto_due.pop(identifier,None)
        _auto_failures.pop(identifier,None)
    return updated


def setup(password, repeat=None):
    if repeat is not None and password!=repeat: raise ValueError('Пароли не совпадают')
    identifier=owner()
    with cloud_traffic.metered(identifier):
        saved=cloud.request('/sync/keyring')['envelope']
        if saved is None:
            _, proposed=make_keyring(identifier,password)
            saved=cloud.request('/sync/keyring',method='PUT',body=proposed)['envelope']
        master=unlock_keyring(identifier,password,saved)
    get_db().set_setting('cloud_sync_key:'+identifier,b64(master))


def key_ready():
    try: return bool(get_db().get_setting('cloud_sync_key:'+owner()))
    except ValueError: return False


def forget_key():
    identifier=owner();save_options({'enabled':False,'auto':False})
    get_db().set_setting('cloud_sync_key:'+identifier,'')


def status():
    try:
        identifier=owner();persisted=json.loads(get_db().get_setting('cloud_sync_status:'+identifier) or '{}')
        return {**persisted,**_status.get(identifier,{})}
    except ValueError: return {}


def ledger_key(identifier): return 'cloud_sync_ledger:'+identifier


def read_ledger(identifier):
    return json.loads(get_db().get_setting(ledger_key(identifier)) or '{"records":{},"cursor":0,"blobs":{},"conflicts":{}}')


def fingerprint(value):
    versions=[]
    if isinstance(value,dict):
        paths=[]
        for message in value.get('messages',[]):
            paths.extend(item[1] for item in message.get('attachments',[]) if isinstance(item,(list,tuple)) and len(item)==2)
        paths.extend(item.get('path','') for item in value.get('materials',[]) if isinstance(item,dict))
        for path in paths:
            file=Path(path)
            stat=file.stat() if path and file.is_file() else None
            versions.append([path,None if stat is None else [stat.st_size,stat.st_mtime_ns]])
    return hashlib.sha256(canonical({'value':value,'file_versions':versions})).hexdigest()


def enabled_scope(scope, opts):
    return opts.get(scope,False)


def run(*, upload_only=False):
    identifier=owner();opts=options(identifier)
    if not opts['enabled']: raise ValueError('Синхронизация выключена')
    secret=get_db().get_setting('cloud_sync_key:'+identifier)
    if not secret: raise ValueError('Введите пароль синхронизации')
    root=app_data_dir();root.mkdir(parents=True,exist_ok=True)
    lease=FileLock(str(root/'cloud-sync.lock'),thread_local=False)
    try: lease.acquire(timeout=0)
    except Timeout: return {'busy':True}
    _status[identifier]={**status(),'running':True,'error':'','phase':'Получаем изменения','next_retry':None}
    try:
        ledger=read_ledger(identifier)
        def save(): get_db().set_setting(ledger_key(identifier),json.dumps(ledger,ensure_ascii=False))
        files=Files(identifier,unb64(secret),ledger,save)
        files.expected_options=opts
        from .sync_entities import Entities
        entities=Entities(identifier,opts,ledger,files,save)
        sent=received=0
        with cloud_traffic.metered(identifier):
            # Persisted operation/envelope is retried verbatim after uncertainty.
            parked=ledger.setdefault('parked',{})
            if ledger.get('pending'):
                pending=ledger['pending']
                if enabled_scope(ledger['records'][pending['key']]['scope'],opts):
                    _flush(ledger,files,save);sent+=1
                else:
                    parked[pending['key']]=ledger.pop('pending');save()
            for key,pending in list(parked.items()):
                if enabled_scope(ledger['records'][key]['scope'],opts):
                    ledger['pending']=parked.pop(key);save()
                    _flush(ledger,files,save);sent+=1
            # Replay old operations first: their acknowledgments must not erase
            # a newer request to publish material content or repaired labels.
            if ledger.get('material_metadata_version',0)<2 or (opts['materials'] and ledger.get('materials_generation',0)!=opts.get('materials_generation',0)):
                for record in ledger['records'].values():
                    if record['scope'] in ('chats','workspaces') and not record.get('deleted'):
                        record['force_upload']=True
                ledger['material_metadata_version']=2
                if opts['materials']:ledger['materials_generation']=opts.get('materials_generation',0)
                save()
            cursor=ledger.get('cursor',0)
            # Collapse history before downloading content: old references to
            # deleted materials must not block the latest version on a new client.
            while True:
                reply=files.request(f'/sync/pull?after={cursor}&limit=20')
                for change in reply['changes']:
                    record_key=change['kind']+':'+change['id']
                    scope=change['data'].get('scope') if not change['deleted'] else ledger.get('known_scopes',{}).get(record_key)
                    if scope:ledger.setdefault('known_scopes',{})[record_key]=scope
                    ledger.setdefault('deferred',{})[record_key]=change
                    ledger['cursor']=change['sequence'];save()
                cursor=reply['cursor']
                if not reply['has_more']:break
            for record_key,change in sorted(list(ledger.get('deferred',{}).items()),key=lambda pair:({'chat':0,'workspace':1,'canvas':2}.get(pair[1]['kind'],3),pair[0])):
                if upload_only:break
                existing=ledger['records'].get(record_key,{})
                scope=(existing.get('scope') or ledger.get('known_scopes',{}).get(record_key)) if change['deleted'] else change['data'].get('scope')
                if scope and enabled_scope(scope,opts):
                    if change['revision']>existing.get('revision',0):
                        payload=None if change['deleted'] else files.decode(change['id'],change['data'])
                        entities.receive(record_key,change,payload);received+=1
                    del ledger['deferred'][record_key];save()
            if not upload_only:
                entities.reconcile_links()
                entities.recover_deleted_chat_conflicts()
            if opts['materials'] and not upload_only:
                from .storage import material_references
                referenced=material_references(get_db())
                trash=json.loads(get_db().get_setting('material_trash_v1') or '{}')
                trashed={str(app_data_dir()/'materials'/i['relative']) for i in trash.values()}
                for path,entry in list(ledger.get('assets',{}).items()):
                    if path in referenced and path not in trashed and path not in json.loads(get_db().get_setting('material_removed_v1') or '{}') and not entry.get('excluded') and not entry['manifest'].get('missing') and not Path(path).is_file():
                        try:restored=files.download_file(entry['manifest'])
                        except cloud.CloudError as exc:
                            if exc.status!=404:raise
                            continue
                        if restored:
                            stat=Path(restored).stat();entry['stamp']=[stat.st_size,stat.st_mtime_ns];save()
            _status[identifier]['phase']='Отправляем изменения'
            for record_key, snapshot in entities.snapshots():
                record=ledger['records'][record_key]
                if record.get('blocked') or (record.get('hash')==snapshot['hash'] and not record.get('force_upload')): continue
                packet={} if snapshot['deleted'] else files.encode(record_key.split(':',1)[1],record['scope'],snapshot['payload'])
                operation=dict(operation_id=str(uuid.uuid4()),entity_id=record_key.split(':',1)[1],kind=record['kind'],
                    base_revision=record.get('revision',0),deleted=snapshot['deleted'],data=packet)
                ledger['pending']={'key':record_key,'hash':snapshot['hash'],'operation':operation};save()
                _flush(ledger,files,save);sent+=1
        result={'running':False,'error':'','phase':'Готово','last_sync':time.time(),'sent':sent,'received':received,
                'conflicts':len(ledger.get('conflicts',{}))}
        _status[identifier]=result
        get_db().set_setting('cloud_sync_status:'+identifier,json.dumps(result))
        return result
    except Exception as exc:
        previous=json.loads(get_db().get_setting('cloud_sync_status:'+identifier) or '{}')
        _status[identifier]={**previous,'running':False,'error':str(exc)}
        get_db().set_setting('cloud_sync_status:'+identifier,json.dumps(_status[identifier]))
        raise
    finally:
        lease.release()


def _flush(ledger,files,save):
    pending=ledger['pending'];op=pending['operation']
    result=files.request('/sync/push',method='POST',body={'operations':[op]})['results'][0]
    record=ledger['records'][pending['key']]
    if result['status']=='conflict':
        current=result['current']
        ledger.setdefault('conflicts',{})[pending['key']]=current
        record['blocked']=True
    else:
        record.update(revision=result['revision'],hash=pending['hash'],force_upload=False)
        if op['deleted']: record['deleted']=True
    del ledger['pending'];save()


def conflict_items():
    return read_ledger(owner()).get('conflicts',{})


def resolve_keep_both(record_key):
    identifier=owner()
    lease=FileLock(str(app_data_dir()/'cloud-sync.lock'),thread_local=False)
    try: lease.acquire(timeout=0)
    except Timeout: raise ValueError('Дождитесь окончания синхронизации') from None
    try:
        ledger=read_ledger(identifier)
        change=ledger['conflicts'][record_key]
        record=ledger['records'][record_key]
        if record['scope'] in ('protected','profile'):
            raise ValueError('Для профиля выберите локальную или облачную версию' if record['scope']=='profile' else 'Для защищённого чата выберите версию после закрытия чата. Обе зашифрованные версии сохранены')
        def save(): get_db().set_setting(ledger_key(identifier),json.dumps(ledger,ensure_ascii=False))
        files=Files(identifier,unb64(get_db().get_setting('cloud_sync_key:'+identifier)),ledger,save)
        with cloud_traffic.metered(identifier):
            payload=None if change['deleted'] else files.decode(record_key.split(':',1)[1],change['data'])
        from .sync_entities import Entities
        bridge=Entities(identifier,options(identifier),ledger,files,save)
        # Preserve the remote branch as a new local item; the original local
        # branch can subsequently publish against the acknowledged revision.
        if payload is not None: bridge.import_copy(record['scope'],payload)
        if change['deleted']:
            replacement=copy.deepcopy(record);replacement.update(revision=0,hash=None,blocked=False,deleted=False)
            new_key=record['kind']+':'+str(uuid.uuid4())
            ledger['records'][new_key]=replacement
            record.update(deleted=True,hash='deleted',local_id=None)
        record.update(revision=change['revision'],blocked=False)
        del ledger['conflicts'][record_key];save()
    finally: lease.release()


_auto_due={}
_auto_failures={}
_auto_dirty=set()
AUTO_INTERVAL = 1
def request_soon():
    """A completed local edit wakes replication without bypassing retry/budget policy."""
    try:identifier=owner()
    except ValueError:return
    with _lock:
        if _auto_due.get(identifier)==float('inf'):
            _auto_dirty.add(identifier)
        elif not _auto_failures.get(identifier):
            _auto_due[identifier]=0


def run_auto_if_due(*, upload_only=False):
    identifier=owner();opts=options(identifier)
    if not opts['enabled'] or not opts['auto']:return None
    with _lock:
        if time.monotonic()<_auto_due.get(identifier,0):return None
        # Reserve the attempt before releasing the lock, including other pages.
        _auto_due[identifier]=float('inf')
    try:
        result=run(upload_only=True) if upload_only else run()
    except Exception:
        with _lock:
            failures=min(_auto_failures.get(identifier,0)+1,6)
            _auto_failures[identifier]=failures
            delay=min(300,15*2**(failures-1))
            _auto_due[identifier]=time.monotonic()+delay
            _status.setdefault(identifier,{})['next_retry']=time.time()+delay
        raise
    else:
        with _lock:
            _auto_failures.pop(identifier,None)
            # Foreground replicas poll once per second for a two-hop target of two seconds. The byte budget and
            # failure backoff still take precedence over this target interval.
            _auto_dirty.discard(identifier)
            delay=AUTO_INTERVAL
            _auto_due[identifier]=time.monotonic()+delay
            _status.setdefault(identifier,{})['next_retry']=None
        return result



def resolve_private(record_key,version):
    if version not in ('local','cloud'):raise ValueError('Выберите версию')
    identifier=owner();lease=FileLock(str(app_data_dir()/'cloud-sync.lock'),thread_local=False)
    try:lease.acquire(timeout=0)
    except Timeout:raise ValueError('Дождитесь окончания синхронизации') from None
    try:
        ledger=read_ledger(identifier);record=ledger['records'][record_key];change=ledger['conflicts'][record_key]
        if record['scope']!='protected':raise ValueError('Это обычный чат')
        def save():get_db().set_setting(ledger_key(identifier),json.dumps(ledger,ensure_ascii=False))
        files=Files(identifier,unb64(get_db().get_setting('cloud_sync_key:'+identifier)),ledger,save)
        from .sync_entities import Entities
        bridge=Entities(identifier,options(identifier),ledger,files,save)
        with cloud_traffic.metered(identifier):
            payload=None if change['deleted'] else files.decode(record_key.split(':',1)[1],change['data'])
        cid=record.get('local_id') or (payload or {}).get('cid')
        if cid is None:raise ValueError('Не найден защищённый чат')
        folder=app_data_dir()/'private-chats'/f'{abs(cid):x}';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        check=FileLock(str(folder/'session.lock'),thread_local=False)
        try:check.acquire(timeout=0)
        except Timeout:raise ValueError('Сначала закройте защищённый чат') from None
        check.release()
        with cloud_traffic.metered(identifier):
            if version=='local':
                if payload is not None:bridge.backup_private_payload(payload)
                if change['deleted']:
                    replacement=copy.deepcopy(record);replacement.update(revision=0,hash=None,blocked=False,deleted=False)
                    ledger['records']['chat:'+str(uuid.uuid4())]=replacement
                    record.update(deleted=True,hash='deleted')
                record.update(revision=change['revision'],blocked=False)
            else:
                record['local_id']=cid
                current=bridge._local(record);record['hash']=None if current is None else fingerprint(current)
                if not bridge._private_apply(record_key,record,change,payload):raise ValueError('Сначала закройте защищённый чат')
                record['blocked']=False
        del ledger['conflicts'][record_key];save()
    finally:lease.release()


def profile_conflict_preview(record_key):
    """Decrypt both versions locally without resolving or changing the profile."""
    identifier=owner()
    with FileLock(str(app_data_dir()/'cloud-sync.lock'),thread_local=False,timeout=0):
        ledger=read_ledger(identifier);record=ledger['records'][record_key];change=ledger['conflicts'][record_key]
        if record['scope']!='profile' or change['deleted']:raise ValueError('Это не конфликт версий профиля')
        from .profile import read,validate
        files=Files(identifier,unb64(get_db().get_setting('cloud_sync_key:'+identifier)),ledger,lambda:None)
        with cloud_traffic.metered(identifier):cloud=validate(files.decode(change['id'],change['data']))
        local=read()
        return {'local':local,'cloud':cloud,'expected':{'local':fingerprint(local),'cloud':fingerprint(cloud)}}


def resolve_profile(record_key,version,*,expected=None):
    if version not in ('local','cloud'):raise ValueError('Выберите версию')
    identifier=owner()
    with FileLock(str(app_data_dir()/'cloud-sync.lock'),thread_local=False,timeout=0):
        ledger=read_ledger(identifier);record=ledger['records'][record_key];change=ledger['conflicts'][record_key]
        if record['scope']!='profile':raise ValueError('Это не профиль')
        def save():get_db().set_setting(ledger_key(identifier),json.dumps(ledger,ensure_ascii=False))
        files=Files(identifier,unb64(get_db().get_setting('cloud_sync_key:'+identifier)),ledger,save)
        with cloud_traffic.metered(identifier):payload=files.decode(change['id'],change['data'])
        from .profile import read,validate
        payload=validate(payload)
        current=read()
        if expected is not None and expected!={'local':fingerprint(current),'cloud':fingerprint(payload)}:
            raise ValueError('Профиль изменился после просмотра. Откройте конфликт заново')
        from .sync_entities import Entities
        bridge=Entities(identifier,options(identifier),ledger,files,save)
        backups=json.loads(get_db().get_setting('profile_recovery_v1') or '[]')
        backups.append({'time':time.time(),'profile':current if version=='cloud' else payload})
        get_db().set_setting('profile_recovery_v1',json.dumps(backups,ensure_ascii=False))
        if version=='cloud':
            record['hash']=fingerprint(current);record['blocked']=False
            if not bridge._apply(record_key,record,change,payload,current):raise ValueError('Профиль изменился, повторите выбор')
        else:record.update(revision=change['revision'],blocked=False,force_upload=True)
        del ledger['conflicts'][record_key];save()
