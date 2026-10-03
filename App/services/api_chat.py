"""OpenAI-compatible Chat Completions transport, selected explicitly by the user."""
import base64
import http.client
import json
import socket
import threading
from concurrent.futures import CancelledError
from urllib.parse import urlsplit
from .db import get_db, get_setting
from .attachments import build_attachment_message_parts
from .llm import DEFAULT_SYSTEM_PROMPT, response_language_instruction
from .stats import record_generation

KEY = 'api_config_v1'


def configuration():
    return json.loads(get_setting(KEY, '{}'))


def validate_configuration(config):
    url = str(config.get('url', '')).strip().rstrip('/')
    parsed = urlsplit(url)
    if parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Введите URL API без ключа, параметров и пароля: https://example.com/v1')
    if parsed.scheme == 'http' and parsed.hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise ValueError('Для удалённого API нужен HTTPS. HTTP доступен для локального сервера.')
    model = str(config.get('model', '')).strip()
    if not model:
        raise ValueError('Введите идентификатор модели API')
    return {'url': url, 'model': model, 'key': str(config.get('key', '')).strip()}


def save_configuration(config):
    value = validate_configuration(config)
    get_db().set_setting(KEY, json.dumps(value, ensure_ascii=False))
    return value


def is_api_selected():
    return get_setting('chat_provider', 'local') == 'api'


def select_api():
    validate_configuration(configuration())
    get_db().set_setting('chat_provider', 'api')


def select_local():
    get_db().set_setting('chat_provider', 'local')


def image_mime(raw):
    if raw.startswith(b'\xff\xd8'):
        return 'image/jpeg'
    if raw.startswith(b'GIF'):
        return 'image/gif'
    if raw.startswith(b'RIFF'):
        return 'image/webp'
    return 'image/png'


def generate_reply(prompt_text, history=None, attachments=None, *, instructions='', cancelled=None):
    config = validate_configuration(configuration())
    if cancelled is not None and cancelled.is_set():
        raise CancelledError()
    notes, images = build_attachment_message_parts(attachments or [])
    text = '\n\n'.join([prompt_text, *notes])
    content = [{'type': 'text', 'text': text}]
    content.extend({'type': 'image_url', 'image_url': {'url': 'data:' + image_mime(raw) + ';base64,' + base64.b64encode(raw).decode('ascii')}} for raw in images)
    messages = [{'role': 'system', 'content': DEFAULT_SYSTEM_PROMPT + response_language_instruction() + '\n' + instructions}]
    messages.extend({'role': 'assistant' if item['role'] in {'ai', 'assistant'} else 'user', 'content': item['content']} for item in (history or []))
    messages.append({'role': 'user', 'content': content if images else text})
    payload = json.dumps({'model': config['model'], 'messages': messages, 'stream': False}, ensure_ascii=False).encode('utf-8')
    parsed = urlsplit(config['url'])
    connection_class = http.client.HTTPSConnection if parsed.scheme == 'https' else http.client.HTTPConnection
    connection = connection_class(parsed.hostname, parsed.port, timeout=120)
    finished = threading.Event()
    active_socket = None

    def monitor():
        while not finished.wait(.1):
            if cancelled is not None and cancelled.is_set():
                sock = connection.sock or active_socket
                if sock:
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                connection.close()
                return

    watcher = threading.Thread(target=monitor, daemon=True)
    watcher.start()
    try:
        path = parsed.path.rstrip('/')
        if not path.endswith('/chat/completions'):
            path += '/chat/completions'
        headers = {'Content-Type': 'application/json'}
        if config['key']:
            headers['Authorization'] = 'Bearer ' + config['key']
        connection.connect()
        active_socket = connection.sock
        if cancelled is not None and cancelled.is_set():
            raise CancelledError()
        connection.request('POST', path, body=payload, headers=headers)
        response = connection.getresponse()
        if response.status >= 400:
            raise RuntimeError(f'API вернул HTTP {response.status}. Проверьте URL, ключ и модель.')
        data = json.loads(response.read())
        text = data['choices'][0]['message']['content']
        if isinstance(text, list):
            text = '\n'.join(part.get('text', '') for part in text if isinstance(part, dict))
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError('API не вернул текст ответа')
        if cancelled is not None and cancelled.is_set():
            raise CancelledError()
        record_generation(text)
        return text.strip()
    except Exception as exc:
        if cancelled is not None and cancelled.is_set():
            raise CancelledError() from exc
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError('Не удалось прочитать ответ API. Проверьте соединение и совместимость Chat Completions.') from exc
    finally:
        finished.set()
        connection.close()
        watcher.join(timeout=.2)
