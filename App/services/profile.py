"""Profile data belongs to SQLCipher and the encrypted profile sync entity."""
import base64
import io
import json
import time
from pathlib import Path
from PIL import Image, ImageOps
from .db import get_db
from .image_safety import open_raster

KEY='profile_v1'
GOOGLE_SOURCE='profile_google_source_v1'
MAX_AVATAR=256*1024

def _google_source(db):
    try:
        value=json.loads(db.get_setting(GOOGLE_SOURCE) or '{}')
        return value if isinstance(value,dict) else {}
    except (ValueError,TypeError):return {}

def manual_source(db):
    return {**_google_source(db),'manual_name':True,'manual_avatar':True}

def needs_google_avatar(url,db=None):
    db=db or get_db();current=read(db);source=_google_source(db)
    return not source.get('manual_avatar') and bool(url) and (not current['avatar'] or current['avatar']==source.get('avatar')) and (
        not current['avatar'] or url!=source.get('picture_url'))

def import_google(account_id,*,name='',avatar=None,picture_url='',db=None):
    """Seed blank fields and refresh Google-derived fields; preserve local/synced edits."""
    db=db or get_db()
    name=''.join(c for c in name if ord(c)>=32 and ord(c)!=127).strip()[:50] if isinstance(name,str) else ''
    for _ in range(3):
        before=db.get_setting(KEY);legacy=db.get_setting('profile_name');raw=db.get_setting(GOOGLE_SOURCE)
        source=_google_source(db);current=read(db);data=dict(current);updated=dict(source)
        if name and not source.get('manual_name') and (current['name']=='Пользователь' or current['name']==source.get('name')):
            data['name']=updated['name']=name
        if avatar is not None and not source.get('manual_avatar') and (not current['avatar'] or current['avatar']==source.get('avatar')):
            data['avatar']=updated['avatar']=avatar;updated['picture_url']=picture_url
        if data==current and updated==source:return current
        updated['account_id']=account_id;data=validate(data)
        if db.apply_sync_settings([(KEY,before),('profile_name',legacy),(GOOGLE_SOURCE,raw)],
                [(KEY,json.dumps(data,ensure_ascii=False)),('profile_name',data['name']),
                 (GOOGLE_SOURCE,json.dumps(updated,ensure_ascii=False))]):return data
    raise ValueError('Профиль изменился. Повторите обновление')

def normalize_avatar(data):
    if len(data)>10*1024*1024:raise ValueError('Выберите изображение до 10 МБ')
    with open_raster(io.BytesIO(data)) as image:
        image=ImageOps.exif_transpose(image).convert('RGB')
        image=ImageOps.fit(image,(256,256),method=Image.Resampling.LANCZOS)
        output=io.BytesIO();image.save(output,format='JPEG',quality=90)
    encoded=base64.b64encode(output.getvalue()).decode('ascii')
    if len(encoded)>MAX_AVATAR:raise ValueError('Изображение слишком большое')
    return encoded

def validate(data):
    name=data.get('name')
    avatar=data.get('avatar','')
    if not isinstance(name,str) or not 1<=len(name.strip())<=50 or any(ord(c)<32 for c in name):raise ValueError('Имя должно содержать от 1 до 50 символов')
    if not isinstance(avatar,str) or len(avatar)>MAX_AVATAR:raise ValueError('Неверная аватарка')
    if avatar:
        decoded=base64.b64decode(avatar,validate=True)
        with open_raster(io.BytesIO(decoded), formats=('JPEG',)) as image:
            if image.size!=(256,256) or image.format!='JPEG':raise ValueError('Неверный формат аватарки')
            image.verify()
    result = {'name':name.strip(),'avatar':avatar}
    if 'memory' in data:
        from .user_memory import validate as validate_memory
        result['memory'] = validate_memory(data['memory'])
    return result

def read(db=None):
    db=db or get_db();raw=db.get_setting(KEY)
    if raw:return validate(json.loads(raw))
    return {'name':db.get_setting('profile_name') or 'Пользователь','avatar':''}

def explicit(db=None):
    db=db or get_db()
    return bool(db.get_setting(KEY) or (db.get_setting('profile_name') not in (None,'','Пользователь')))

def update(*,name=None,avatar=None):
    db=get_db()
    for _ in range(3):
        before=db.get_setting(KEY);legacy=db.get_setting('profile_name');data=read(db)
        source_raw=db.get_setting(GOOGLE_SOURCE);source=_google_source(db)
        if name is not None:data['name']=name
        if avatar is not None:data['avatar']=avatar
        if name is not None:source['manual_name']=True
        if avatar is not None:source['manual_avatar']=True
        data=validate(data)
        if db.apply_sync_settings([(KEY,before),('profile_name',legacy),(GOOGLE_SOURCE,source_raw)],
            [(KEY,json.dumps(data,ensure_ascii=False)),('profile_name',data['name']),
             (GOOGLE_SOURCE,json.dumps(source,ensure_ascii=False))]):return data
    raise ValueError('Профиль изменился. Повторите сохранение')

def set_avatar(*,path=None,data=None):
    if data is None:
        path=Path(path)
        if path.stat().st_size>10*1024*1024:raise ValueError('Выберите изображение до 10 МБ')
        data=path.read_bytes()
    return update(avatar=normalize_avatar(data))

def recoveries():
    return list(enumerate(json.loads(get_db().get_setting('profile_recovery_v1') or '[]')))

def restore_recovery(index):
    db=get_db()
    for _ in range(3):
        raw=db.get_setting('profile_recovery_v1');items=json.loads(raw or '[]')
        selected=validate(items[index]['profile'])
        before=db.get_setting(KEY);legacy=db.get_setting('profile_name');current=read(db)
        source_raw=db.get_setting(GOOGLE_SOURCE);source=manual_source(db)
        items.append({'time':time.time(),'profile':current})
        if db.apply_sync_settings([(KEY,before),('profile_name',legacy),('profile_recovery_v1',raw),(GOOGLE_SOURCE,source_raw)],
                [(KEY,json.dumps(selected,ensure_ascii=False)),('profile_name',selected['name']),('profile_recovery_v1',json.dumps(items,ensure_ascii=False)),
                 (GOOGLE_SOURCE,json.dumps(source,ensure_ascii=False))]):return selected
    raise ValueError('Профиль изменился. Повторите восстановление')
