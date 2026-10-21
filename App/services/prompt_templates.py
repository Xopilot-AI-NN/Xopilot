"""
Файл: /App/services/prompt_templates.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Сохраняю личные шаблоны запросов в локальной зашифрованной БД.
"""
import json
import time
import uuid
from .db import get_db

KEY='prompt_templates_v1'


def _read(db):
    value=json.loads(db.get_setting(KEY) or '[]')
    if not isinstance(value,list):raise ValueError('Неверные данные шаблонов')
    for item in value:
        if not isinstance(item,dict) or not isinstance(item.get('title'),str) or not isinstance(item.get('body'),str):
            raise ValueError('Неверная запись шаблона')
        uuid.UUID(item['id'])
        if type(item.get('updated')) not in (int,float) or not 0<=item['updated']<10**12:raise ValueError('Неверная дата шаблона')
    return value


def list_templates(query=''):
    needle=str(query).strip().casefold()
    return sorted([dict(item) for item in _read(get_db()) if needle in (item['title']+'\n'+item['body']).casefold()],key=lambda item:item['updated'],reverse=True)


def save(title,body,identifier=None):
    if not isinstance(title,str) or not 1<=len(title.strip())<=80 or any(ord(c)<32 for c in title):raise ValueError('Введите название до 80 символов')
    if not isinstance(body,str) or not body.strip() or len(body)>20000:raise ValueError('Введите текст шаблона до 20 000 символов')
    key=str(uuid.UUID(identifier)) if identifier else str(uuid.uuid4());db=get_db()
    for _ in range(5):
        before=db.get_setting(KEY);items=_read(db)
        if identifier and not any(item['id']==key for item in items):raise ValueError('Шаблон уже удалён')
        value=[item for item in items if item['id']!=key]
        value.append(dict(id=key,title=title.strip(),body=body,updated=time.time()))
        if db.apply_sync_settings([(KEY,before)],[(KEY,json.dumps(value,ensure_ascii=False))]):return key
    raise RuntimeError('Шаблоны изменились. Повторите сохранение')


def delete(identifier):
    key=str(uuid.UUID(identifier));db=get_db()
    for _ in range(5):
        before=db.get_setting(KEY);items=_read(db);value=[item for item in items if item['id']!=key]
        if len(items)==len(value):return False
        if db.apply_sync_settings([(KEY,before)],[(KEY,json.dumps(value,ensure_ascii=False))]):return True
    raise RuntimeError('Шаблоны изменились. Повторите удаление')


def insert(draft,body):
    """Подставляю текст без отправки и без потери уже набранного черновика."""
    return draft+'\n\n'+body if draft else body
