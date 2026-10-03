"""Chat drafts use the same encrypted database as messages."""
import json
from .db import get_db


def read_draft(chat_id):
    raw = get_db().get_setting(f'draft:{chat_id}')
    return json.loads(raw) if raw else {'text': '', 'files': []}


def write_draft(chat_id, text, files):
    if chat_id is None:
        return
    get_db().set_setting(f'draft:{chat_id}', json.dumps({'text': text, 'files': files}, ensure_ascii=False))
