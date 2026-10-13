"""Chunked encrypted material transport. Originals and cleartext paths stay local."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
import time
import uuid
from . import cloud_account as cloud
from .paths import app_data_dir
from .sync_crypto import seal, open_sealed, b64, unb64, canonical

CHUNK = 4 * 1024 * 1024


class Files:
    def __init__(self, owner, key, ledger, save):
        self.owner, self.key, self.ledger, self.save = owner, key, ledger, save
        self.root = app_data_dir() / 'cloud-cache' / owner
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def request(self, path, **kwargs):
        from .cloud_sync import options
        for attempt in range(3):
            account=cloud.state()
            if not account or account['account_id']!=self.owner:
                raise RuntimeError('Аккаунт сменился. Синхронизация остановлена')
            current=options(self.owner)
            if not current['enabled']:raise RuntimeError('Синхронизация выключена')
            expected=getattr(self,'expected_options',None)
            if expected and any(current[name]!=expected[name] for name in ('profile','chats','workspaces','canvases','materials','protected')):
                raise RuntimeError('Выбор данных изменился. Повторите синхронизацию')
            try:return cloud.request(path, **kwargs)
            except cloud.CloudError as exc:
                if exc.code!='connection_failed' or attempt==2:raise
                # Push operation IDs and encrypted PUT bytes remain unchanged;
                # each retry is metered and rechecks the user's current choices.
                time.sleep(0.5*2**attempt)

    def put_chunk(self, block):
        # Other devices may have advanced the generation after deleting a blob.
        # A tombstone cannot be overwritten; find the next valid identity.
        while True:
            identifier=self._put_chunk(block)
            if identifier is not None:return identifier

    def _put_chunk(self, block):
        signature=hashlib.sha256(block).hexdigest()
        identifier=str(uuid.UUID(bytes=hmac.digest(self.key, b'blob:'+signature.encode()+b':'+str(self.ledger.setdefault('blob_generations',{}).get(signature,0)).encode(), 'sha256')[:16]))
        blobs=self.ledger.setdefault('blobs',{})
        entry=blobs.setdefault(identifier, {'digest':signature, 'uploaded':False, 'bytes':len(block)})
        if identifier in self.ledger.get('excluded_blobs',[]):
            raise ValueError('Этот материал исключён из облачного хранилища')
        if entry['uploaded']: return identifier
        cache=self.root/identifier
        if not cache.exists():
            from .private_chats import _atomic
            _atomic(cache,seal(self.key,self.owner,identifier,block))
        encrypted=cache.read_bytes()
        try:
            result=self.request('/files/'+identifier+'?sha256='+hashlib.sha256(encrypted).hexdigest(),method='PUT',raw=encrypted)
        except cloud.CloudError as exc:
            if exc.code!='file_id_reused': raise
            # A retry from a second device may have encrypted the same block
            # with a different nonce. Authenticate the existing server copy.
            try:existing=self.request('/files/'+identifier,binary=True)
            except cloud.CloudError as missing:
                if missing.status!=404:raise
                self.ledger['blob_generations'][signature]=self.ledger['blob_generations'].get(signature,0)+1
                self.save();cache.unlink(missing_ok=True)
                return None
            if hashlib.sha256(open_sealed(self.key,self.owner,identifier,existing,CHUNK)).hexdigest()!=signature:
                raise ValueError('Конфликт идентификатора зашифрованного файла') from None
            result={'bytes':len(existing)}
        entry.update(uploaded=True,stored_bytes=result['bytes'])
        self.save()
        cache.unlink(missing_ok=True)
        return identifier

    def get_chunk(self, identifier):
        identifier=str(uuid.UUID(identifier))
        data=self.request('/files/'+identifier,binary=True)
        block=open_sealed(self.key,self.owner,identifier,data,CHUNK)
        self.ledger.setdefault('blobs',{})[identifier]={'digest':hashlib.sha256(block).hexdigest(),'uploaded':True,'bytes':len(block),'stored_bytes':len(data)}
        self.save()
        return block

    def upload_file(self, name, path):
        path=Path(path)
        if not path.is_file(): return {'name':name,'missing':True}
        before=path.stat()
        if before.st_size>512*1024*1024:
            raise ValueError('Материал превышает допустимый размер одного исходного файла (512 МБ)')
        parts=[]; checksum=hashlib.sha256()
        with path.open('rb') as source:
            while block:=source.read(CHUNK):
                checksum.update(block)
                parts.append(self.put_chunk(block))
        after=path.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise RuntimeError('Материал изменился во время отправки. Повторите синхронизацию')
        return {'name':Path(name.replace('\\','/')).name,'size':before.st_size,'sha256':checksum.hexdigest(),'chunks':parts}

    def download_file(self, asset, *, destination=None):
        if asset.get('missing'): return ''
        name=Path(asset['name'].replace('\\','/')).name
        if name in ('','.','..') or not isinstance(asset.get('size'),int) or not 0<=asset['size']<=512*1024*1024:
            raise ValueError('Неверное описание материала')
        parts=asset['chunks']
        if not isinstance(parts,list) or len(parts)>128: raise ValueError('Неверные блоки материала')
        root=app_data_dir()/'materials'; root.mkdir(parents=True,exist_ok=True)
        fd, staging=tempfile.mkstemp(prefix='.incoming-',dir=root)
        total=0; checksum=hashlib.sha256()
        try:
            with os.fdopen(fd,'wb') as output:
                for part in parts:
                    block=self.get_chunk(part)
                    total+=len(block)
                    if total>asset['size']: raise ValueError('Неверный размер материала')
                    checksum.update(block);output.write(block)
                output.flush();os.fsync(output.fileno())
            if total!=asset['size'] or checksum.hexdigest()!=asset['sha256']:
                raise ValueError('Материал не прошёл проверку целостности')
            if destination is None:
                folder=root/checksum.hexdigest();folder.mkdir(exist_ok=True)
                destination=folder/name
            destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            os.replace(staging,destination)
            return str(destination)
        finally:
            Path(staging).unlink(missing_ok=True)

    def encode(self, identifier, scope, payload):
        raw=canonical({'identifier':identifier,'scope':scope,'payload':payload})
        if len(raw)<12000:
            return {'version':1,'scope':scope,'ciphertext':b64(seal(self.key,self.owner,identifier,raw))}
        # Chunk bodies keep even long chats outside PostgreSQL JSON and within
        # the HTTP packet limit. Each block is compressed before encryption.
        parts=[self.put_chunk(raw[i:i+CHUNK]) for i in range(0,len(raw),CHUNK)]
        return {'version':1,'scope':scope,'chunks':parts,'size':len(raw)}

    def decode(self, identifier, envelope):
        if envelope.get('version')!=1: raise ValueError('Неизвестный формат облачных данных')
        if 'ciphertext' in envelope:
            raw=open_sealed(self.key,self.owner,identifier,unb64(envelope['ciphertext']),CHUNK)
        else:
            size=envelope['size'];parts=envelope['chunks']
            if not isinstance(size,int) or not 0<=size<=512*1024*1024 or len(parts)>128:
                raise ValueError('Неверный размер облачных данных')
            blocks=[];total=0
            for part in parts:
                block=self.get_chunk(part);total+=len(block)
                if total>size: raise ValueError('Неверные блоки облачных данных')
                blocks.append(block)
            raw=b''.join(blocks)
            if len(raw)!=size: raise ValueError('Неверный размер облачных данных')
        result=json.loads(raw)
        if result.get('identifier')!=identifier or result['scope']!=envelope['scope']: raise ValueError('Неверная категория облачных данных')
        return result['payload']
