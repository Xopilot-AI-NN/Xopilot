"""Account-bound authenticated encryption; bounded decompression occurs after authentication."""
import base64
import gzip
import json
import os
import zlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.exceptions import InvalidTag


def b64(data):
    return base64.b64encode(data).decode('ascii')


def unb64(value):
    return base64.b64decode(value, validate=True)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def aad(owner, identifier):
    return f'Xopilot/sync/v1/{owner}/{identifier}'.encode('ascii')


def seal(key, owner, identifier, data):
    compressed = gzip.compress(data, compresslevel=6, mtime=0)
    packed = b'G' + compressed if len(compressed) < len(data) else b'P' + data
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, packed, aad(owner, identifier))


def open_sealed(key, owner, identifier, data, max_bytes=16*1024*1024):
    if len(data) < 29:
        raise ValueError('Повреждённые данные синхронизации')
    try:
        packed = AESGCM(key).decrypt(data[:12], data[12:], aad(owner, identifier))
    except InvalidTag:
        raise ValueError('Не удалось проверить подлинность данных синхронизации') from None
    if packed[:1] == b'P':
        result = packed[1:]
    elif packed[:1] == b'G':
        decoder = zlib.decompressobj(16+zlib.MAX_WBITS)
        result = decoder.decompress(packed[1:], max_bytes+1)
        if decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:
            raise ValueError('Неверный размер сжатых данных')
    else:
        raise ValueError('Неизвестный формат синхронизации')
    if len(result) > max_bytes:
        raise ValueError('Данные превышают допустимый размер блока')
    return result


def make_keyring(owner, password):
    if len(password) < 12 or len(password.encode()) > 1024:
        raise ValueError('Пароль синхронизации должен содержать не меньше 12 символов')
    salt, master = os.urandom(16), os.urandom(32)
    wrapping = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode())
    nonce = os.urandom(12)
    envelope = dict(version=1, kdf='scrypt-32768-8-1', salt=b64(salt), nonce=b64(nonce),
        ciphertext=b64(AESGCM(wrapping).encrypt(nonce, master, aad(owner,'keyring'))))
    return master, envelope


def unlock_keyring(owner, password, envelope):
    try:
        if envelope['version'] != 1 or envelope['kdf'] != 'scrypt-32768-8-1':
            raise ValueError()
        salt, nonce, ciphertext = (unb64(envelope[k]) for k in ('salt','nonce','ciphertext'))
        if len(salt)!=16 or len(nonce)!=12 or len(ciphertext)!=48 or len(password.encode())>1024:
            raise ValueError()
        wrapping=Scrypt(salt=salt,length=32,n=2**15,r=8,p=1).derive(password.encode())
        return AESGCM(wrapping).decrypt(nonce,ciphertext,aad(owner,'keyring'))
    except (KeyError, TypeError, ValueError, InvalidTag):
        raise ValueError('Неверный пароль синхронизации или повреждённый ключ') from None
