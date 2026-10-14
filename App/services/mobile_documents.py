"""
Файл: /App/services/mobile_documents.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Восстановление выбранных файлов и экспортов Android без потери черновиков.
"""
import asyncio
import re
import os
import tempfile
import uuid
from pathlib import Path
from .mobile_runtime import call_async
from .db import get_db
from .drafts import read_draft, write_draft
from .material_store import store_material
from .paths import app_data_dir


async def import_selection(operation):
    if not operation:
        return None
    token = operation['token']
    if operation.get('state') == 'error':
        await call_async('ackDocuments', {'token': token})
        raise RuntimeError(operation.get('error') or 'Не удалось получить выбранные файлы')
    if operation.get('state') != 'ready':
        return None
    if operation.get('tag') == 'export':
        await call_async('ackDocuments', {'token': token})
        return {'exported': bool(operation.get('exported'))}
    if operation.get('tag') == 'avatar':
        from . import profile
        entries = operation.get('files', [])
        if entries:
            try:
                await asyncio.to_thread(profile.set_avatar, path=entries[0]['path'])
            except (ValueError, OSError):
                # An invalid/oversized image cannot succeed on retry. Discard
                # only its staged picker copy so another selection can start.
                await call_async('ackDocuments', {'token': token})
                raise
        await call_async('ackDocuments', {'token': token})
        return {'profile': bool(entries)}
    workspace = re.fullmatch(r'workspace:([0-9a-f-]{32,36})', operation.get('tag', ''))
    if workspace:
        from . import library, workspaces
        identifier = workspace[1]
        uuid.UUID(identifier)
        if not any(item['id'] == identifier for item in workspaces.list_workspaces()):
            await call_async('ackDocuments', {'token': token})
            return None
        materials = []
        for entry in operation.get('files', []):
            path = await asyncio.to_thread(store_material, entry['name'], path=entry['path'])
            materials.append({'name': entry['name'], 'path': path, 'enabled': True})
        await asyncio.to_thread(library.append_materials, identifier, materials)
        await call_async('ackDocuments', {'token': token})
        return {'workspace_id': identifier, 'files': [item['path'] for item in materials]}
    match = re.fullmatch(r'chat:([1-9][0-9]*)', operation.get('tag', ''))
    chat_id = int(match[1]) if match else None
    # Never redirect a removed chat's selection to the current chat, nor import
    # into a protected/temporary store that is locked after process death.
    if chat_id is None or not any(row[0] == chat_id for row in get_db().list_chats()):
        await call_async('ackDocuments', {'token': token})
        return None
    files = []
    for entry in operation.get('files', []):
        files.append(await asyncio.to_thread(store_material, entry['name'], path=entry['path']))
    draft = read_draft(chat_id)
    merged = list(dict.fromkeys([*draft.get('files', []), *files]))
    write_draft(chat_id, draft.get('text', ''), merged)
    # A restart between the DB write and acknowledgement is idempotent: the
    # managed store uses content hashes, and the draft removes duplicates.
    await call_async('ackDocuments', {'token': token})
    return {'chat_id': chat_id, 'files': files}


async def pick_chat_documents(chat_id):
    await _recover_before_new_operation()
    result = await import_selection(await call_async('pickDocuments', {'tag': f'chat:{chat_id}'}))
    if result and result.get('chat_id') == chat_id:
        # Include files recovered immediately before this selection, so the UI
        # cannot overwrite them when it next persists its attachment strip.
        result['files'] = read_draft(chat_id).get('files', [])
    return result


async def pick_workspace_documents(workspace_id):
    uuid.UUID(workspace_id)
    await _recover_before_new_operation()
    return await import_selection(await call_async('pickDocuments', {'tag': f'workspace:{workspace_id}'}))


async def pick_avatar():
    await _recover_before_new_operation()
    return await import_selection(await call_async('pickDocuments', {'tag': 'avatar'}))


async def recover_pending_documents():
    operation = await call_async('pendingDocuments')
    # Activity results and copying can arrive while the new Python app starts.
    for _ in range(50):
        if not operation or operation.get('state') not in ('waiting', 'copying'):
            return await import_selection(operation)
        await asyncio.sleep(0.2)
        operation = await call_async('pendingDocuments')
    # Do not discard a slow copy. A later launch can complete its recovery.
    return None


async def _recover_before_new_operation():
    operation = await call_async('pendingDocuments')
    if operation and operation.get('state') == 'copying':
        await recover_pending_documents()
    elif operation and operation.get('state') in ('ready', 'error'):
        await import_selection(operation)


async def save_document(name, data):
    await _recover_before_new_operation()
    root = app_data_dir() / 'export_staging'
    root.mkdir(parents=True, exist_ok=True)
    descriptor, path = tempfile.mkstemp(dir=root)
    try:
        def write():
            with os.fdopen(descriptor, 'wb') as output:
                output.write(data)
        await asyncio.to_thread(write)
        token = await call_async('stageExport', {'path': path, 'name': name})
    finally:
        Path(path).unlink(missing_ok=True)
    result = await import_selection(await call_async('exportDocument', {'token': token}))
    return bool(result and result.get('exported'))


async def save_document_file(name, path):
    """Stage and export with native streaming; no whole-file Python/Flutter copy."""
    await _recover_before_new_operation()
    token = await call_async('stageExport', {'path': str(path), 'name': name})
    result = await import_selection(await call_async('exportDocument', {'token': token}))
    return bool(result and result.get('exported'))
