"""Файл: /App/services/model_context.py
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: Размер окна API-модели из метаданных провайдера, без передачи переписки.
"""
import hashlib
import http.client
import json
import re
import threading
import time
from collections import OrderedDict
from types import SimpleNamespace
from urllib.parse import quote, urlsplit

_cache = OrderedDict()
_lock = threading.Lock()


def _key(config):
    return (config['url'], config['model'], hashlib.sha256(config.get('key', '').encode()).hexdigest())


def engine(config):
    """None means unknown; no model-name guesses or arbitrary API window caps."""
    key = _key(config)
    with _lock:
        previous = _cache.get(key)
        if previous and previous[0] > time.monotonic():
            return previous[1]
    host = urlsplit(config['url']).hostname
    value = None
    if host in {'openrouter.ai', 'generativelanguage.googleapis.com'}:
        connection = http.client.HTTPSConnection(host, timeout=5)
        try:
            headers = {'Accept': 'application/json'}
            path = '/api/v1/models'
            if host == 'generativelanguage.googleapis.com':
                path = '/v1beta/models/' + quote(config['model'].removeprefix('models/'), safe='')
                headers['x-goog-api-key'] = config.get('key', '')
            connection.request('GET', path, headers=headers)
            response = connection.getresponse()
            if response.status == 200:
                raw = response.read(8 * 1024 * 1024 + 1)
                if len(raw) <= 8 * 1024 * 1024:
                    data = json.loads(raw)
                    if host == 'openrouter.ai':
                        limit = next((m.get('context_length') for m in data.get('data', [])
                                      if m.get('id') == config['model']), None)
                    else:
                        limit = data.get('inputTokenLimit')
                    if type(limit) is int and 512 <= limit <= 100_000_000:
                        output = (data.get('outputTokenLimit') if host != 'openrouter.ai' else
                                  next(((m.get('top_provider') or {}).get('max_completion_tokens')
                                        for m in data.get('data', []) if m.get('id') == config['model']), None))
                        value = SimpleNamespace(max_num_tokens=limit,
                            max_output_tokens=output if type(output) is int and output >= 48 else None,
                            reasoning_supported=(next((('reasoning' in m.get('supported_parameters',[]) or 'reasoning_effort' in m.get('supported_parameters',[]))
                                for m in data.get('data',[]) if m.get('id')==config['model']),False) if host=='openrouter.ai' else None))
        except (OSError, ValueError, TypeError, AttributeError, http.client.HTTPException):
            pass
        finally:
            connection.close()
    if host not in {'openrouter.ai','generativelanguage.googleapis.com'}:
        # The configured origin alone receives the key, never a third-party catalog.
        parsed=urlsplit(config['url'])
        connection_class=http.client.HTTPSConnection if parsed.scheme=='https' else http.client.HTTPConnection
        connection=connection_class(parsed.hostname,parsed.port,timeout=5)
        try:
            headers={'Accept':'application/json'}
            if config.get('key'):headers['Authorization']='Bearer '+config['key']
            connection.request('GET',parsed.path.rstrip('/')+'/models',headers=headers)
            response=connection.getresponse()
            if response.status==200:
                raw=response.read(8*1024*1024+1)
                if len(raw)<=8*1024*1024:
                    data=json.loads(raw)
                    for model in data.get('data',[]):
                        if not isinstance(model,dict):continue
                        aliases=model.get('aliases',[])
                        if model.get('id')!=config['model'] and not (isinstance(aliases,list) and config['model'] in aliases):continue
                        meta=model.get('meta') if isinstance(model.get('meta'),dict) else {}
                        # n_ctx is the running slot limit; n_ctx_train can be much larger.
                        candidates=(meta.get('n_ctx'),model.get('n_ctx'),model.get('context_length'),model.get('max_model_len'),model.get('context_window'))
                        limit=next((v for v in candidates if type(v) is int and 512<=v<=100_000_000),None)
                        if limit is not None:
                            value=SimpleNamespace(max_num_tokens=limit,max_output_tokens=None)
                        break
        except (OSError,ValueError,TypeError,AttributeError,http.client.HTTPException):
            pass
        finally:connection.close()
    with _lock:
        _cache[key] = (time.monotonic() + (300 if value else 30), value)
        _cache.move_to_end(key)
        while len(_cache) > 32:
            _cache.popitem(last=False)
    return value


def learn_error(config, message):
    """Accept an explicit provider limit, never the size of the rejected request."""
    patterns = [r'maximum context length (?:is|of)\s*([\d,]+)',
                r'maximum number of tokens allowed:\s*\d+\s*>=\s*(\d+)',
                r'exceeds? the maximum number of tokens allowed\s*\(([\d,]+)\)']
    for pattern in patterns:
        match = re.search(pattern, message, re.I)
        if match:
            limit = int(match[1].replace(',', ''))
            if 512 <= limit <= 100_000_000:
                with _lock:
                    key = _key(config)
                    previous = _cache.get(key)
                    if previous and previous[1] is not None:
                        limit = min(limit, previous[1].max_num_tokens)
                    _cache[key] = (time.monotonic() + 300, SimpleNamespace(max_num_tokens=limit))
                return limit
    return None
