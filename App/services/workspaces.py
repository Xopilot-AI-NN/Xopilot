"""
Файл: App/services/workspaces.py
Разработчик: DenBroLiik
Описание: Сохраняемые коллекции чатов в зашифрованной БД; удаление коллекции сохраняет чаты.
"""

import json
import uuid
import threading
from functools import wraps

_state_lock = threading.RLock()

def locked(method):
    @wraps(method)
    def invoke(*args, **kwargs):
        with _state_lock:
            return method(*args, **kwargs)
    return invoke

from .db import get_db

KEY = "workspaces_v1"
DEFAULT = "all"
ICONS = {'folder': 'Папка', 'code': 'Код', 'book': 'Книга', 'science': 'Наука',
         'brush': 'Творчество', 'work': 'Работа', 'school': 'Учёба', 'music': 'Музыка',
         'travel': 'Путешествия', 'rocket': 'Запуск', 'heart': 'Личное', 'lightbulb': 'Идеи'}

def validate_icon(icon):
    if icon not in ICONS:
        raise ValueError('Выберите иконку проекта из списка')
    return icon



def _read():
    raw = get_db().get_setting(KEY)
    return json.loads(raw) if raw else {"items": [], "chats": {}, "selected": DEFAULT}


def _write(state):
    get_db().set_setting(KEY, json.dumps(state, ensure_ascii=False))


@locked
def list_workspaces():
    state = _read()
    return [{"id": DEFAULT, "name": "Все чаты"}, *state["items"]]


@locked
def selected_workspace():
    state = _read()
    return state["selected"] if state["selected"] in {DEFAULT, *(i["id"] for i in state["items"])} else DEFAULT


@locked
def create_workspace(name, instructions='', materials=None, icon='folder'):
    name = name.strip()
    if not name:
        raise ValueError("Введите название пространства")
    state = _read()
    item = {"id": uuid.uuid4().hex, "name": name,
            "icon": validate_icon(icon), "instructions": instructions.strip(), "materials": [dict(m) for m in (materials or [])]}
    state["items"].append(item)
    _write(state)
    return item


@locked
def rename_workspace(identifier, name):
    name = name.strip()
    if not name:
        raise ValueError("Введите название пространства")
    state = _read()
    item = next((i for i in state["items"] if i["id"] == identifier), None)
    if item is None:
        raise ValueError("Пространство не найдено")
    item["name"] = name
    _write(state)


@locked
def select_workspace(identifier):
    state = _read()
    if identifier not in {DEFAULT, *(i["id"] for i in state["items"])}:
        raise ValueError("Пространство не найдено")
    state["selected"] = identifier
    _write(state)


@locked
def delete_workspace(identifier):
    if identifier == DEFAULT:
        raise ValueError("Общий список чатов нельзя удалить")
    state = _read()
    state["items"] = [i for i in state["items"] if i["id"] != identifier]
    state["chats"] = {cid: wid for cid, wid in state["chats"].items() if wid != identifier}
    if state["selected"] == identifier:
        state["selected"] = DEFAULT
    _write(state)


@locked
def assign_chat(chat_id, identifier):
    state = _read()
    if identifier not in {DEFAULT, *(i["id"] for i in state["items"])}:
        raise ValueError("Пространство не найдено")
    state["chats"][str(chat_id)] = identifier
    _write(state)


@locked
def filter_chats(chats, identifier=None):
    state = _read()
    identifier = identifier or state["selected"]
    if identifier == DEFAULT:
        return chats
    return [chat for chat in chats if state["chats"].get(str(chat[0])) == identifier]


@locked
def chat_workspace(chat_id):
    state = _read()
    identifier = state['chats'].get(str(chat_id), DEFAULT)
    return next((dict(i) for i in state['items'] if i['id'] == identifier),
                {'id': DEFAULT, 'name': 'Все чаты', 'instructions': '', 'materials': []})


@locked
def update_workspace(identifier, name, instructions='', materials=None, icon=None):
    name = name.strip()
    if not name:
        raise ValueError('Введите название пространства')
    state = _read()
    item = next((i for i in state['items'] if i['id'] == identifier), None)
    if item is None:
        raise ValueError('Пространство не найдено')
    item.update(name=name, instructions=instructions.strip())
    if icon is not None:
        item['icon'] = validate_icon(icon)
    if materials is not None:
        item['materials'] = [dict(m) for m in materials]
    _write(state)


@locked
def chat_resources(chat_id):
    item = chat_workspace(chat_id)
    return item.get('instructions', ''), [(m['name'], m['path']) for m in item.get('materials', []) if m.get('enabled', True)]


@locked
def forget_chat(chat_id):
    state = _read()
    state['chats'].pop(str(chat_id), None)
    _write(state)
