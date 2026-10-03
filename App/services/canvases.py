"""Persistent text, code and drawing documents in the encrypted settings store."""
import copy
import io
import json
import threading
import time
import uuid
from .db import get_db

KEY = 'canvases_v1'
_lock = threading.RLock()
KINDS = {'text', 'code', 'drawing'}


def _read():
    return json.loads(get_db().get_setting(KEY) or '[]')


def list_documents(chat_id=None, workspace_id=None):
    with _lock:
        return [copy.deepcopy(doc) for doc in _read()
                if chat_id is None or doc.get('chat_id') == chat_id
                or (workspace_id and workspace_id != 'all' and doc.get('workspace_id') == workspace_id)]


def get_document(identifier):
    with _lock:
        doc = next((item for item in _read() if item['id'] == identifier), None)
        if doc is None:
            raise ValueError('Canvas не найден')
        return copy.deepcopy(doc)


def create_document(title='Новый Canvas', kind='text', content='', *, chat_id=None, workspace_id='all', source_request=None):
    if kind not in KINDS:
        raise ValueError('Неизвестный тип Canvas')
    with _lock:
        docs = _read()
        if source_request is not None:
            existing = next((doc for doc in docs if doc.get('source_request') == source_request
                             and doc['title'] == title.strip() and doc['kind'] == kind and doc['content'] == content), None)
            if existing:
                return copy.deepcopy(existing)
        item = dict(id=uuid.uuid4().hex, title=title.strip() or 'Новый Canvas', kind=kind,
                    content=content, strokes=[], chat_id=chat_id, workspace_id=workspace_id,
                    updated_at=time.time())
        if source_request is not None:
            item['source_request'] = source_request
        docs.append(item)
        get_db().set_setting(KEY, json.dumps(docs, ensure_ascii=False))
        return copy.deepcopy(item)


def save_document(document):
    if document.get('kind') not in KINDS or not document.get('title', '').strip():
        raise ValueError('Введите название Canvas')
    with _lock:
        docs = _read()
        index = next((i for i, item in enumerate(docs) if item['id'] == document['id']), None)
        if index is None:
            raise ValueError('Canvas не найден')
        docs[index] = {**copy.deepcopy(document), 'updated_at': time.time()}
        get_db().set_setting(KEY, json.dumps(docs, ensure_ascii=False))
        return copy.deepcopy(docs[index])


def export_document(document):
    title = document['title'].replace('/', '_').replace('\\', '_')
    if document['kind'] != 'drawing':
        return title + ('.py' if document['kind'] == 'code' else '.md'), document.get('content', '').encode('utf-8')
    from PIL import Image, ImageDraw
    import math
    logical_width, logical_height = document.get('drawing_size', [1200, 700])
    if not all(isinstance(n, (int, float)) and math.isfinite(n) and n > 0 for n in (logical_width, logical_height)):
        raise ValueError('Неверный размер рисунка')
    scale = min(1200 / logical_width, 1200 / logical_height)
    image_width, image_height = max(1, round(logical_width * scale)), max(1, round(logical_height * scale))
    image = Image.new('RGB', (image_width, image_height), 'white')
    draw = ImageDraw.Draw(image)
    for stroke in document.get('strokes', []):
        points = [(round(x * image_width), round(y * image_height)) for x, y in stroke['points']]
        ink = stroke['color']
        width = max(1, round(stroke.get('width', 3) * scale))
        if len(points) > 1:
            draw.line(points, fill=ink, width=width, joint='curve')
        for x, y in (points[:1] + points[-1:]):
            draw.ellipse((x-width/2, y-width/2, x+width/2, y+width/2), fill=ink)
    output = io.BytesIO()
    image.save(output, 'PNG')
    return title + '.png', output.getvalue()
