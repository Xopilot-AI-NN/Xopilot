"""
Файл: /App/services/chat_search.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Поиск и постраничное чтение обычных чатов по запросу ИИ.
          Защищённая и временная история не открывается этим модулем.
"""
import re
from .db import get_db
from . import workspaces


def recent(*, exclude_chat_id=None, offset=0, limit=20):
    """Недавние обычные чаты по последнему сообщению, без текущего диалога."""
    rows=[]
    for identifier,title,created in get_db().list_chats():
        if identifier<=0 or identifier==exclude_chat_id:continue
        messages=get_db().get_messages(identifier)
        rows.append((max((m.id for m in messages),default=0),created,identifier,title))
    rows.sort(reverse=True)
    offset=max(0,int(offset));limit=max(1,min(50,int(limit)))
    return {'chats':[{'chat_id':identifier,'title':title,'created_at':created}
                     for _,created,identifier,title in rows[offset:offset+limit]],
            'next_offset':offset+limit if len(rows)>offset+limit else None}


def search(query, *, after_chat_id=0, limit=20):
    query = str(query).strip()
    if not query: raise ValueError('Укажите слова для поиска чата')
    limit = max(1, min(50, int(limit)))
    words = re.findall(r'\w+', query.casefold())
    result = []
    for identifier, title, created in sorted(get_db().list_chats()):
        if identifier <= max(0, int(after_chat_id)): continue
        matches = []
        title_match = query.casefold() in title.casefold() or all(word in title.casefold() for word in words)
        for message in get_db().get_messages(identifier):
            text = message.content.casefold()
            if query.casefold() in text or all(word in text for word in words):
                position = text.find(words[0]) if words else 0
                matches.append({'message_id': message.id, 'role': message.role,
                                'excerpt': message.content[max(0, position-80):position+600]})
                if len(matches) == 3: break
        if title_match or matches:
            result.append({'chat_id': identifier, 'title': title,
                           'workspace': workspaces.chat_workspace(identifier)['name'],
                           'created_at': created, 'matches': matches})
            if len(result) >= limit: break
    return {'chats': result, 'next_after_chat_id': result[-1]['chat_id'] if len(result) == limit else None}


def read(chat_id, *, after_message_id=0):
    identifier = int(chat_id)
    chat = next((row for row in get_db().list_chats() if row[0] == identifier and identifier > 0), None)
    if chat is None: raise ValueError('Обычный чат не найден')
    rows, used, next_cursor = [], 0, None
    messages = [m for m in get_db().get_messages(identifier) if m.id > int(after_message_id)]
    for message in messages:
        # Paging is a tool-output bound; it does not truncate stored history.
        if rows and used + len(message.content) > 24000:
            next_cursor = rows[-1]['message_id']; break
        rows.append({'message_id': message.id, 'role': message.role, 'content': message.content,
                     'attachments': [name for name, _ in message.attachments]})
        used += len(message.content)
    return {'chat_id': identifier, 'title': chat[1], 'messages': rows, 'next_after_message_id': next_cursor}
