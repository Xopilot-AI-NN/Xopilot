"""
Файл: /App/services/api_chat.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Совместимый API чата, отмена запросов и восстановимые ошибки провайдера.
"""
"""OpenAI-compatible Chat Completions transport, selected explicitly by the user."""
import base64
import http.client
import json
import socket
import io
import threading
import time
from concurrent.futures import CancelledError
from urllib.parse import urlsplit
from .task_control import network_error, RateLimitedError, EmptyModelReplyError
from .db import get_db, get_setting
from .attachments import build_attachment_message_parts


class _CancellableReader(io.RawIOBase):
    """Poll cancellation inside raw reads, preserving HTTP/TLS buffering.

    Socket shutdown from another thread does not reliably wake Winsock's
    timeout wait. A timeout here stays inside readinto; BufferedReader never
    sees one and can continue parsing partial headers/chunks safely.
    """
    def __init__(self, sock, cancelled):
        self.sock = sock
        self.cancelled = cancelled
        self.lease = sock.makefile('rb', buffering=0)
        sock.settimeout(.25)

    def readable(self):
        return True

    def readinto(self, buffer):
        deadline = time.monotonic() + 120
        while True:
            if self.cancelled is not None and self.cancelled.is_set():
                raise CancelledError()
            try:
                return self.sock.recv_into(buffer)
            except socket.timeout:
                if time.monotonic() >= deadline:
                    raise TimeoutError('API response timed out') from None

    def close(self):
        try:
            self.lease.close()
        finally:
            super().close()


class _ResponseSocket:
    def __init__(self, sock, cancelled):
        self.sock, self.cancelled = sock, cancelled

    def makefile(self, _mode):
        return io.BufferedReader(_CancellableReader(self.sock, self.cancelled))
from .llm import DEFAULT_SYSTEM_PROMPT, response_language_instruction
from .stats import record_generation

KEY = 'api_config_v1'
PROVIDERS = {
    'google': ('Google AI Studio · Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai'),
    'openrouter': ('OpenRouter', 'https://openrouter.ai/api/v1'),
    'custom': ('Другой совместимый API', ''),
}
_modality_cache = (0.0, {})
_modality_lock = threading.Lock()
_image_rejected = set()


def image_support(config):
    """True/False from the provider catalog; None when capabilities are unknown.

    Only image requests need this lookup. Never send keys or chat content to the
    public catalog, and never infer capabilities from a model's name.
    """
    global _modality_cache
    if (config['url'], config['model']) in _image_rejected:
        return False
    if provider_for(config) != 'openrouter':
        return None
    with _modality_lock:
        expires, models = _modality_cache
        if time.monotonic() >= expires:
            # Back off failed catalog lookups; unknown models still use their
            # normal transport, so an unavailable catalog cannot block chat.
            _modality_cache = (time.monotonic() + 30, {})
            connection = http.client.HTTPSConnection('openrouter.ai', timeout=5)
            try:
                connection.request('GET', '/api/v1/models', headers={'Accept': 'application/json'})
                response = connection.getresponse()
                if response.status != 200:
                    return None
                raw = response.read(8 * 1024 * 1024 + 1)
                if len(raw) > 8 * 1024 * 1024:
                    return None
                models = {}
                for item in json.loads(raw)['data']:
                    modalities = item.get('architecture', {}).get('input_modalities')
                    if isinstance(modalities, list) and modalities:
                        models[item['id']] = 'image' in modalities
                _modality_cache = (time.monotonic() + 300, models)
            except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
                return None
            finally:
                connection.close()
        return models.get(config['model'])


def provider_for(config):
    host = urlsplit(config.get('url', '')).hostname
    return 'google' if host == 'generativelanguage.googleapis.com' else 'openrouter' if host == 'openrouter.ai' else 'custom'


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
    _image_rejected.discard((value['url'], value['model']))
    _screen_fallback_until.pop((value['url'], value['model']), None)
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


_json_unsupported=set()
_screen_fallback_until={}


class ProviderUnavailableError(RuntimeError):
    pass


def generate_reply(prompt_text, history=None, attachments=None, *, instructions='', cancelled=None, structured=False, screen_attachments=None):
    for attempt in range(3):
        try:
            return _generate_reply(prompt_text,history,attachments,instructions=instructions,cancelled=cancelled,structured=structured,screen_attachments=screen_attachments)
        except ProviderUnavailableError:
            if attempt==2:raise
            if cancelled is not None:
                if cancelled.wait(1+attempt):raise CancelledError()
            else:
                import time
                time.sleep(1+attempt)


def _generate_reply(prompt_text, history=None, attachments=None, *, instructions='', cancelled=None, structured=False, screen_attachments=None, _summary_budget=None, _config=None, _context_retry=False):
    config = _config if _config is not None else validate_configuration(configuration())
    if cancelled is not None and cancelled.is_set():
        raise CancelledError()
    screen_key=(config['url'],config['model'])
    if screen_attachments and _screen_fallback_until.get(screen_key,0)>time.monotonic():
        remaining=[f for f in (attachments or []) if tuple(f) not in {tuple(x) for x in screen_attachments}]
        return _generate_reply(prompt_text,history,remaining,instructions=instructions+'\nЭкран этой модели недоступен; используй только controls доступности.',cancelled=cancelled,structured=structured)
    notes, images = build_attachment_message_parts(attachments or [])
    if images and image_support(config) is False:
        if screen_attachments:
            remaining=[f for f in (attachments or []) if tuple(f) not in {tuple(x) for x in screen_attachments}]
            return _generate_reply(prompt_text,history,remaining,instructions=instructions+'\nКадр экрана недоступен выбранной модели. Используй только наблюдаемые controls доступности; не утверждай, что видел изображение.',cancelled=cancelled,structured=structured)
        raise RuntimeError('Выбранная модель не поддерживает изображения. '
                           'Выберите модель с поддержкой изображений или выключите камеру/экран и уберите изображения из вложений.')
    if cancelled is not None and cancelled.is_set():
        raise CancelledError()
    text = '\n\n'.join([prompt_text, *notes])
    content = [{'type': 'text', 'text': text}]
    content.extend({'type': 'image_url', 'image_url': {'url': 'data:' + image_mime(raw) + ';base64,' + base64.b64encode(raw).decode('ascii')}} for raw in images)
    system = instructions if _summary_budget is not None else DEFAULT_SYSTEM_PROMPT + response_language_instruction() + '\n' + instructions
    recent = [{'role': 'assistant' if item['role'] in {'ai', 'assistant', 'model'} else 'user',
               'content': item['content']} for item in (history or [])]
    current = {'role': 'user', 'content': content if images else text}
    if _summary_budget is None and recent:
        from . import model_context, context_budget
        context_engine = model_context.engine(config)
        if context_engine is not None:
            def summarize(instruction, source, target):
                return _generate_reply(source, instructions=instruction, cancelled=cancelled,
                                       _summary_budget=target, _config=config)
            recent = context_budget.prepare(context_engine, system, recent, current, summarize,
                                             cancelled=cancelled)
    messages = [{'role': 'system', 'content': system}, *recent, current]
    body={'model': config['model'], 'messages': messages, 'stream': False}
    if _summary_budget is not None:
        body['max_tokens'] = _summary_budget
    format_key=(config['url'],config['model'])
    if structured and format_key not in _json_unsupported:body['response_format']={'type':'json_object'}
    payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
    parsed = urlsplit(config['url'])
    connection_class = http.client.HTTPSConnection if parsed.scheme == 'https' else http.client.HTTPConnection
    connection = connection_class(parsed.hostname, parsed.port, timeout=10)
    connection.response_class = lambda sock, **kwargs: http.client.HTTPResponse(
        _ResponseSocket(sock, cancelled), **kwargs)
    finished = threading.Event()
    active_socket = None
    response = None

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
        connection.sock.settimeout(120)
        # Keep an independently owned handle: HTTPConnection closes its socket
        # when a response uses Connection: close, before its body has arrived.
        # SSLSocket deliberately has no dup(); duplicate only its underlying
        # transport for shutdown, and detach the temporary owner immediately.
        transport = socket.socket(fileno=connection.sock.fileno())
        try:
            active_socket = transport.dup()
        finally:
            transport.detach()
        if cancelled is not None and cancelled.is_set():
            raise CancelledError()
        connection.request('POST', path, body=payload, headers=headers)
        response = connection.getresponse()
        if response.status >= 400:
            import logging
            logging.getLogger(__name__).warning('HTTP %s',response.status)
            error_body = response.read(65536) if response.status in {400, 413, 415, 422} else b''
            reason = error_body.decode('utf-8', errors='replace').casefold()
            rejected_image = images and response.status in {400, 415, 422} and any(
                word in reason for word in ('image', 'vision', 'multimodal')) and any(
                word in reason for word in ('not support', 'unsupported', 'text only', 'text-only'))
            if rejected_image:
                _image_rejected.add(screen_key)
                if screen_attachments:
                    remaining=[f for f in (attachments or []) if tuple(f) not in {tuple(x) for x in screen_attachments}]
                    return _generate_reply(prompt_text, history, remaining,
                        instructions=instructions+'\nМодель не поддерживает изображения. Используй только controls доступности; не утверждай, что видел экран.',
                        cancelled=cancelled, structured=structured, _config=config)
                raise RuntimeError('Выбранная модель не поддерживает изображения. Выберите модель с поддержкой vision.')
            if response.status in {400, 413} and not _context_retry and _summary_budget is None and history:
                from . import model_context
                raw_error = error_body
                try:
                    error = json.loads(raw_error).get('error', {})
                    message = error.get('message', '') if isinstance(error, dict) else str(error)
                except (ValueError, AttributeError):
                    message = ''
                if model_context.learn_error(config, message):
                    return _generate_reply(prompt_text, history, attachments, instructions=instructions,
                        cancelled=cancelled, structured=structured, screen_attachments=screen_attachments,
                        _config=config, _context_retry=True)
            if response.status==400 and 'response_format' in body:
                reason=error_body.decode('utf-8',errors='replace').casefold()
                if any(word in reason for word in ('response_format','json_object','structured')) and any(
                        word in reason for word in ('unsupported','not supported','unknown','unrecognized')):
                    _json_unsupported.add(format_key)
                    return generate_reply(prompt_text,history,attachments,instructions=instructions,cancelled=cancelled)
            if response.status == 429:
                raise RateLimitedError('Лимит запросов API (HTTP 429). Повторите позже или выберите другую модель.')
            if response.status >= 500:
                if images and 'response_format' in body and not screen_attachments:
                    _json_unsupported.add(format_key)
                    return _generate_reply(prompt_text,history,attachments,instructions=instructions,cancelled=cancelled,structured=False,screen_attachments=screen_attachments)
                if screen_attachments:
                    remaining=[f for f in (attachments or []) if tuple(f) not in {tuple(x) for x in screen_attachments}]
                    result = _generate_reply(prompt_text,history,remaining,instructions=instructions+'\nПровайдер отклонил кадр экрана. Продолжай по настоящим controls доступности в результатах computer_view; изображение не было просмотрено.',cancelled=cancelled,structured=False)
                    _screen_fallback_until[screen_key]=time.monotonic()+300
                    return result
                raise ProviderUnavailableError(f'Провайдер ИИ вернул HTTP {response.status}. Запрос повторён без выполнения действий на ПК. Если ошибка повторяется при просмотре экрана, выберите модель с поддержкой изображений.')
            raise RuntimeError(f'API вернул HTTP {response.status}. Проверьте URL, ключ и модель.')
        data = json.loads(response.read())
        text = data['choices'][0]['message']['content']
        if isinstance(text, list):
            text = '\n'.join(part.get('text', '') for part in text if isinstance(part, dict))
        if not isinstance(text, str) or not text.strip():
            raise EmptyModelReplyError('API не вернул текст ответа')
        if cancelled is not None and cancelled.is_set():
            raise CancelledError()
        if _summary_budget is None:
            record_generation(text)
        return text.strip()
    except Exception as exc:
        if cancelled is not None and cancelled.is_set():
            raise CancelledError() from exc
        if network_error(exc):
            raise ConnectionError('Потеряно соединение с API') from exc
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError('Не удалось прочитать ответ API. Проверьте соединение и совместимость Chat Completions.') from exc
    finally:
        finished.set()
        if response is not None:
            response.close()
        connection.close()
        watcher.join(timeout=.2)
        if active_socket is not None:
            active_socket.close()
