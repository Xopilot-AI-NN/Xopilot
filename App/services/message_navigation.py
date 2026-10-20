"""
Файл: /App/services/message_navigation.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Ищу сообщения и сохраняю локальные закладки без копирования текста переписки.
"""
import json
import time
from .db import get_db

KEY='message_bookmarks_v1'


def _marks(db):
    value=json.loads(db.get_setting(KEY) or '{}')
    if not isinstance(value,dict):raise ValueError('Неверные данные закладок')
    return value


def marked(message_id):
    try:return str(message_id) in _marks(get_db())
    except (ValueError,TypeError):return False


def _messages(chat_id):
    db=get_db()
    if chat_id<=0 or not any(row[0]==chat_id for row in db.list_chats()):raise ValueError('Обычный чат не найден')
    return [m for m in db.get_messages(chat_id) if m.role in ('user','ai') and not m.content.startswith('[XOPILOT_ACTION_V1]')]


def toggle(chat_id,message_id):
    db=get_db()
    if not any(m.id==message_id for m in _messages(chat_id)):raise ValueError('Сообщение больше недоступно')
    for _ in range(5):
        before=db.get_setting(KEY);marks=_marks(db);key=str(message_id)
        saved=key not in marks
        if saved:marks[key]={'chat_id':chat_id,'created_at':time.time()}
        else:marks.pop(key,None)
        if db.apply_sync_settings([(KEY,before)],[(KEY,json.dumps(marks))]):return saved
    raise RuntimeError('Закладки изменились. Повторите действие')


def search(chat_id,query='',*,bookmarks=False,offset=0,limit=30):
    if type(offset) is not int or offset<0:raise ValueError('Неверная страница')
    needle=str(query).strip().casefold();marks=_marks(get_db()) if bookmarks else {}
    matches=[]
    for msg in _messages(chat_id):
        if bookmarks and marks.get(str(msg.id),{}).get('chat_id')!=chat_id:continue
        text=msg.content
        if not needle and not bookmarks:continue
        pos=text.casefold().find(needle) if needle else 0
        if pos<0:continue
        start=max(0,pos-70)
        matches.append({'chat_id':chat_id,'message_id':msg.id,'role':msg.role,'created_at':msg.created_at,
                        'excerpt':('…' if start else '')+text[start:start+260]+('…' if start+260<len(text) else '')})
    matches.reverse();limit=max(1,min(100,int(limit)))
    return {'items':matches[offset:offset+limit],'total':len(matches),'next_offset':offset+len(matches[offset:offset+limit]),'has_more':offset+limit<len(matches)}
