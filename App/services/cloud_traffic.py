"""Reserve outgoing application bytes before transport, including failed/retried attempts."""
import contextlib
import json
import threading
import time
from .db import get_db
_context = threading.local()
_lock = threading.RLock()


def key(owner): return 'cloud_traffic_v1:' + owner


def usage(owner):
    with _lock:
        raw=get_db().get_setting(key(owner))
        now=time.time()
        entries=[item for item in json.loads(raw or '[]') if item[0]>now-86400]
        return sum(item[1] for item in entries)


def reserve(size):
    owner=getattr(_context,'owner',None)
    if not owner: return
    with _lock:
        options=json.loads(get_db().get_setting('cloud_sync_options:'+owner) or '{}')
        now=time.time()
        entries=[item for item in json.loads(get_db().get_setting(key(owner)) or '[]') if item[0]>now-86400]
        limit=int(options.get('daily_limit_bytes',10*1024*1024))
        if options.get('traffic_limit',False) and sum(item[1] for item in entries)+size>limit:
            raise RuntimeError('Достигнут лимит отправки за последние 24 часа')
        entries.append([now,size])
        get_db().set_setting(key(owner),json.dumps(entries))


@contextlib.contextmanager
def metered(owner):
    previous=getattr(_context,'owner',None)
    _context.owner=owner
    try: yield
    finally: _context.owner=previous
