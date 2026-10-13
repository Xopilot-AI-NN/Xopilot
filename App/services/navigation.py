"""Non-secret settings navigation, restored after Android process eviction."""
import json
from .db import get_setting, set_setting

KEY = 'navigation_v1'


def read():
    try:
        data = json.loads(get_setting(KEY, '{}'))
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def save(**changes):
    data = {**read(), **changes}
    set_setting(KEY, json.dumps(data, ensure_ascii=False))


def clear():
    set_setting(KEY, '{}')
