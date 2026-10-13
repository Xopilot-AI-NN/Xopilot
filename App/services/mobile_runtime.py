"""Async Flet platform bridge with a blocking facade for inference workers."""
import asyncio
import threading
import json
from pathlib import Path

_service = None
_loop = None
_loop_thread = None
_capabilities = {}


async def initialize():
    global _service, _loop, _loop_thread
    from flet_xopilot_mobile import XopilotMobile
    from .paths import app_data_dir
    from .db import configure_mobile_key, get_db
    _service = XopilotMobile()
    _loop = asyncio.get_running_loop()
    _loop_thread = threading.get_ident()
    database = app_data_dir() / 'xopilot.db'
    key = await _service.call('databaseKey', {'existing': database.exists() and database.stat().st_size > 0})
    configure_mobile_key(key)
    await asyncio.to_thread(get_db)
    try:
        info=await _service.call('deviceInfo')
        if isinstance(info,dict) and isinstance(info.get('name'),str):
            await asyncio.to_thread(get_db().set_setting,'device_info_v1',json.dumps(info))
    except Exception:pass
    # Do not initialize LiteRT/JNI just to label installed files on the home
    # screen. Verified metadata survives process eviction in the encrypted DB.
    await refresh_capabilities(inspect_missing=False)


def _cached(path):
    from .db import get_db
    raw = get_db().get_setting('mobile_model_capabilities_v1')
    try:
        entries = json.loads(raw or '{}')
        entry = entries.get(str(path), {})
        value = entry.get('modalities', {})
        if entry.get('stamp') == list(_identity(path)[1:]) and all(type(value.get(key)) is bool for key in ('audio', 'vision')):
            return value
    except (ValueError, TypeError, AttributeError):
        pass
    return None


def _remember(path, modalities):
    from .db import get_db
    db = get_db()
    try:
        entries = json.loads(db.get_setting('mobile_model_capabilities_v1') or '{}')
        if not isinstance(entries, dict):entries = {}
    except (ValueError, TypeError):entries = {}
    entries[str(path)] = {'stamp': list(_identity(path)[1:]), 'modalities': modalities}
    db.set_setting('mobile_model_capabilities_v1', json.dumps(entries))


async def refresh_capabilities(*, inspect_missing=True):
    from .llm import list_local_models, get_model_path
    for name in list_local_models():
        path = get_model_path(name)
        try:
            value = await asyncio.to_thread(_cached, path)
            if value is None and inspect_missing:
                value = await _service.call('capabilities', {'path': path})
                await asyncio.to_thread(_remember, path, value)
            if value is not None:
                _capabilities[_identity(path)] = value
        except Exception:
            # A broken model must not prevent access to saved chats/settings.
            continue


def _identity(path):
    stat = Path(path).stat()
    return (str(path), stat.st_size, stat.st_mtime_ns)


async def call_async(method, arguments=None):
    if _service is None:
        raise RuntimeError('Служба Android недоступна')
    return await _service.call(method, arguments)


def bind_viewport(page, changed):
    def apply(data):
        height = data.get('height') if isinstance(data, dict) else None
        keyboard = data.get('keyboard', 0) if isinstance(data, dict) else 0
        keyboard = keyboard if isinstance(keyboard, (int, float)) and keyboard >= 0 else 0
        if isinstance(height, (int, float)) and height >= 0 and (
            page.__dict__.get('_xopilot_available_height') != height or
            page.__dict__.get('_xopilot_keyboard_height') != keyboard):
            page.__dict__['_xopilot_available_height'] = height
            page.__dict__['_xopilot_keyboard_height'] = keyboard
            changed()

    _service.on_metrics = lambda event: apply(event.data)
    _service.update()

    async def watch():
        # Flet service events can be missed while the Activity resizes. Keep a
        # bounded fallback; only a changed height causes a page update.
        while True:
            try:
                apply(await call_async('viewportMetrics'))
            except Exception:
                pass
            await asyncio.sleep(0.3)

    page.run_task(watch)


def call(method, arguments=None):
    if _service is None or _loop is None or _loop.is_closed():
        raise RuntimeError('Служба Android недоступна')
    if threading.get_ident() == _loop_thread:
        raise RuntimeError('Операция модели должна выполняться в рабочем потоке')
    # Flet returns native errors to this worker. The event loop remains free to
    # render updates, navigate and deliver cancellation during inference.
    future = asyncio.run_coroutine_threadsafe(_service.call(method, arguments), _loop)
    return future.result(timeout=605)


def capabilities(path):
    identity = _identity(path)
    if identity not in _capabilities:
        value = _cached(path)
        if value is None:
            value = call('capabilities', {'path': str(path)})
            _remember(path, value)
        _capabilities[identity] = value
    return dict(_capabilities[identity])
