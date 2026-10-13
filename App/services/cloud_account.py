"""Account transport. Credentials are kept only in the encrypted local database.

This module deliberately never reads chats/materials/API keys. Content sync is
enabled separately by the user with its own E2EE password.
"""
import json
import os
import platform
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .db import get_db

DEFAULT_ENDPOINT = os.environ.get('XOPILOT_ACCOUNT_ENDPOINT', 'https://xopilot.by')
KEY = 'cloud_account_v1'
_lock = threading.RLock()
ERRORS = {
    'invalid_device_name':'Введите название устройства от 1 до 120 символов',
    'invalid_credentials': 'Неверная почта или пароль',
    'invalid_email': 'Введите действительный адрес почты',
    'email_unavailable': 'Эта почта уже зарегистрирована. Войдите в аккаунт',
    'email_delivery_unavailable': 'Отправка писем пока не настроена. Регистрация станет доступна после подключения SMTP',
    'invalid_verification_code': 'Неверный код подтверждения',
    'verification_expired': 'Код истёк. Начните регистрацию заново',
    'verification_locked': 'Слишком много неверных кодов. Начните регистрацию заново',
    'request_blocked': 'Защита сайта отклонила запрос приложения. Проверьте настройки доступа к API на сервере',
    'invalid_session': 'Сессия завершена. Войдите снова',
    'username_unavailable': 'Этот логин уже занят',
    'registration_closed': 'Регистрация пока закрыта на сервере',
    'password_length': 'Пароль должен содержать от 12 символов и не более 1024 байт',
    'invalid_username': 'Имя пользователя должно содержать от 2 до 50 символов',
    'invalid_device': 'Введите название устройства',
    'try_later': 'Слишком много попыток. Повторите через минуту',
    'storage_unavailable': 'База сервера временно недоступна',
    'connection_failed': 'Нет соединения с сервером. Проверьте адрес и сеть',
    'invalid_response': 'Сервер вернул непонятный ответ',
    'quota_exceeded': 'Облачное хранилище заполнено. Освободите место в управлении хранилищем',
    'not_found': 'Файл отсутствует в облаке',
    'google_not_configured': 'Вход через Google пока не настроен на сервере',
    'google_unavailable': 'Google временно недоступен. Повторите вход позже',
    'google_invalid_flow': 'Не удалось подтвердить вход Google. Начните заново',
    'google_expired': 'Время входа Google истекло. Начните заново',
    'google_denied': 'Вход Google отменён или отклонён',
    'google_account_exists': 'Аккаунт с этой почтой уже есть. Войдите по паролю и выберите «Привязать Google»',
    'google_already_linked': 'Этот Google-аккаунт уже привязан к другому аккаунту, либо у вас уже привязан другой Google-аккаунт',
    'payments_not_configured': 'DonationAlerts ещё не подключён на сервере',
    'payment_provider_unavailable': 'Не удалось проверить оплату в DonationAlerts. Повторите позже',
    'invalid_plan': 'Неизвестный тариф',
    'active_plan_conflict': 'Дождитесь окончания действующего тарифа для перехода на другой',
    'pending_order_conflict': 'Сначала завершите или отмените предыдущий заказ',
    'receipt_already_used': 'Этот платёж уже использован. Обратитесь в поддержку',
    'order_not_pending': 'Заказ уже оплачен, отменён или истёк',
}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward account credentials or Authorization to another URL.
        return None


class CloudError(Exception):
    def __init__(self, code, status=0):
        self.code, self.status = code, status
        super().__init__(ERRORS.get(code, 'Не удалось выполнить запрос к серверу'))


def normalize_endpoint(value):
    value = (value or DEFAULT_ENDPOINT).strip().rstrip('/')
    parts = urlsplit(value)
    if parts.username or parts.password or parts.query or parts.fragment or parts.path:
        raise ValueError('Укажите адрес сервера без пути, пароля и параметров')
    local = parts.hostname in ('localhost', '127.0.0.1', '::1')
    if not parts.hostname or (parts.scheme != 'https' and not (local and parts.scheme == 'http')):
        raise ValueError('Для облачного сервера требуется HTTPS')
    return value


def _read():
    raw = get_db().get_setting(KEY)
    return json.loads(raw) if raw else None


def _save(session):
    get_db().set_setting(KEY, json.dumps(session, ensure_ascii=False) if session else '')


def state():
    with _lock:
        saved = _read()
        if not saved:
            return None
        # Never hand tokens to presentation controls or caller logs.
        return {k: saved.get(k, '') for k in ('account_id', 'session_id', 'username', 'display_name', 'email', 'endpoint', 'device_name', 'google_linked', 'google_profile_warning')}


def _download_google_avatar(url):
    # No Xopilot credentials, cookies, redirects or arbitrary remote hosts.
    parts=urlsplit(url)
    if (len(url)>2048 or parts.scheme!='https' or not re.fullmatch(r'lh\d{1,2}\.googleusercontent\.com',parts.hostname or '')
            or parts.username or parts.password or parts.port not in (None,443) or parts.fragment
            or any(ord(c)<32 for c in url)):
        raise ValueError('Неверный адрес фото Google')
    from . import cloud_traffic,profile
    cloud_traffic.reserve(len(url.encode())+256)
    with build_opener(_NoRedirect()).open(Request(url,headers={'User-Agent':'Xopilot/2.0','Accept':'image/*'}),timeout=12) as response:
        data=response.read(2*1024*1024+1)
    if len(data)>2*1024*1024:raise ValueError('Фото Google слишком большое')
    return profile.normalize_avatar(data)


def _import_google_profile(saved,info):
    details=info.get('google_profile')
    if not isinstance(details,dict):return ''
    from . import profile
    avatar=None;warning='';url=details.get('picture_url') or '';db=get_db()
    try:
        if profile.needs_google_avatar(url,db):avatar=_download_google_avatar(url)
    except Exception:
        warning='Фото Google не удалось загрузить. Нажмите «Обновить данные Google» для повторной попытки.'
    try:profile.import_google(saved['account_id'],name=details.get('name',''),avatar=avatar,picture_url=url,db=db)
    except Exception:
        warning='Не удалось обновить профиль. Ваш вход сохранён; повторите обновление данных Google.'
    return warning


def refresh_google_profile():
    with _lock:
        saved=_read()
        if not saved or not saved.get('google_linked'):return ''
        info=request('/me')
        saved=_read()  # request may rotate tokens; retain the latest session.
        if not saved:return ''
        saved['google_profile_warning']=_import_google_profile(saved,info)
        _save(saved)
        return saved['google_profile_warning']


def _request(endpoint, path, *, method='GET', body=None, token=None, raw=None, binary=False):
    headers = {'Accept': 'application/json', 'User-Agent': 'Xopilot/2.0'}
    data = raw
    if raw is not None:
        headers['Content-Type'] = 'application/octet-stream'
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = Request(normalize_endpoint(endpoint) + '/api/v1' + path, data=data, headers=headers, method=method)
    from . import cloud_traffic
    # Application byte budget includes HTTP request text and encrypted payload;
    # TLS/TCP overhead is outside this counter. Failed attempts remain charged.
    cloud_traffic.reserve(len(data or b'') + len(request.full_url.encode()) +
                          sum(len(k.encode())+len(v.encode())+4 for k,v in headers.items()) + 64)
    try:
        # Standard TLS certificate validation is mandatory, including custom URLs.
        with build_opener(_NoRedirect()).open(request, timeout=20) as response:
            limit = 52 * 1024 * 1024 if binary else 2 * 1024 * 1024
            raw = response.read(limit + 1)
            if len(raw) > limit:
                raise CloudError('invalid_response')
            return raw if binary else json.loads(raw)
    except HTTPError as exc:
        try:
            raw = exc.read(8192)
            code = json.loads(raw).get('error', 'server_error')
        except (ValueError, UnicodeError):
            code = 'request_blocked' if exc.code == 403 else 'server_error'
        finally:
            exc.close()
        raise CloudError(code, exc.code) from None
    except (URLError, TimeoutError, OSError):
        raise CloudError('connection_failed') from None
    except (ValueError, UnicodeError):
        raise CloudError('invalid_response') from None


def _email(value):
    value = (value or '').strip().lower()
    if len(value) > 254 or not value.isascii() or not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", value):
        raise CloudError('invalid_email')
    return value


def _device():
    from .platforms import is_android
    if is_android():
        try:return (json.loads(get_db().get_setting('device_info_v1') or '{}').get('name') or 'Android')[:120]
        except (ValueError,TypeError):return 'Android'
    return (platform.node() or platform.system())[:120]


def _persist_login(endpoint, tokens):
    try:
        profile = _request(endpoint, '/me', token=tokens['access_token'])
        saved = {**tokens, **{k: profile[k] for k in ('username', 'display_name', 'email')},
                 'google_linked': bool(profile.get('google_linked')),
                 'endpoint': endpoint, 'device_name': _device(),
                 'expires_at': time.time() + tokens['expires_in']}
        _save(saved)
    except Exception:
        try:
            _request(endpoint, '/auth/logout', method='POST', token=tokens['access_token'])
        except Exception:
            pass
        raise
    # Import failure must not revoke an otherwise valid account session.
    saved['google_profile_warning']=_import_google_profile(saved,profile)
    try:_save(saved)
    except Exception:pass
    return state()


def begin_google(*, endpoint=DEFAULT_ENDPOINT, link=False):
    import hashlib
    import secrets
    import uuid
    from urllib.parse import parse_qs
    endpoint = normalize_endpoint(endpoint)
    proof = secrets.token_hex(32)
    with _lock:
        saved = _read()
        if link:
            if not saved:
                raise CloudError('invalid_session', 401)
            endpoint = saved['endpoint']
        elif saved:
            raise ValueError('Сначала выйдите из текущего аккаунта')
        body = {'proof_hash': hashlib.sha256(proof.encode()).hexdigest(), 'device_name': _device(), 'link': link}
        pending = request('/auth/google/start', method='POST', body=body) if link else _request(endpoint, '/auth/google/start', method='POST', body=body)
        try:
            flow_id = str(uuid.UUID(pending['flow_id']))
            url = urlsplit(pending['browser_url'])
            origin = urlsplit(endpoint)
            ticket = parse_qs(url.query, strict_parsing=True)
            if (url.scheme, url.netloc) != (origin.scheme, origin.netloc) or url.fragment or url.path != '/api/v1/auth/google/open/' + flow_id:
                raise ValueError()
            if set(ticket) != {'ticket'} or len(ticket['ticket']) != 1 or not re.fullmatch('[0-9a-f]{64}', ticket['ticket'][0]):
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise CloudError('invalid_response') from None
        # Proof is ephemeral, never persisted, logged, or put into the browser URL.
        return {'flow_id': flow_id, 'proof': proof, 'endpoint': endpoint,
                'browser_url': pending['browser_url'], 'link': link,
                'account_id': saved['account_id'] if saved else None,
                'session_id': saved['session_id'] if saved else None}


def poll_google(pending):
    with _lock:
        saved = _read()
        if pending['link']:
            if not saved or (saved['account_id'], saved['session_id']) != (pending['account_id'], pending['session_id']):
                raise CloudError('invalid_session', 401)
        elif saved:
            raise ValueError('Вход в другой аккаунт уже выполнен')
        result = _request(pending['endpoint'], '/auth/google/poll', method='POST',
                          body={k: pending[k] for k in ('flow_id', 'proof')})
        status = result.get('status')
        if status == 'pending':
            return False
        if status == 'failed':
            raise CloudError(result.get('error', 'google_invalid_flow'))
        if status == 'linked' and pending['link']:
            saved['google_linked'] = True
            _save(saved)
            try:refresh_google_profile()
            except Exception:pass
            return True
        if status == 'authenticated' and not pending['link']:
            _persist_login(pending['endpoint'], result['tokens'])
            return True
        raise CloudError('invalid_response')


def cancel_google(pending):
    with _lock:
        _request(pending['endpoint'], '/auth/google/cancel', method='POST',
                 body={k: pending[k] for k in ('flow_id', 'proof')})


def sign_in(email, password, *, endpoint=DEFAULT_ENDPOINT):
    endpoint = normalize_endpoint(endpoint)
    with _lock:
        if _read():
            raise ValueError('Сначала выйдите из текущего аккаунта')
        tokens = _request(endpoint, '/auth/login', method='POST',
                          body={'email': _email(email), 'password': password, 'device_name': _device()})
        return _persist_login(endpoint, tokens)


def begin_registration(username, email, password, repeat_password, *, endpoint=DEFAULT_ENDPOINT):
    username = (username or '').strip()
    if not 2 <= len(username) <= 50 or any(ord(c) < 32 or ord(c) == 127 for c in username):
        raise CloudError('invalid_username')
    email = _email(email)
    if password != repeat_password:
        raise ValueError('Пароли не совпадают')
    if len(password) < 12 or len(password.encode('utf-8')) > 1024:
        raise CloudError('password_length')
    with _lock:
        if _read():
            raise ValueError('Сначала выйдите из текущего аккаунта')
        # A pending registration is not a login; never save passwords or codes.
        return _request(endpoint, '/auth/register', method='POST',
                        body={'username': username, 'email': email, 'password': password, 'device_name': _device()})


def confirm_registration(registration_id, code, *, endpoint=DEFAULT_ENDPOINT):
    import uuid
    registration_id = str(uuid.UUID(registration_id))
    code = (code or '').strip()
    if not re.fullmatch(r'[0-9]{6}', code):
        raise ValueError('Введите 6 цифр из письма')
    with _lock:
        if _read():
            raise ValueError('Сначала выйдите из текущего аккаунта')
        tokens = _request(endpoint, '/auth/verify-email', method='POST',
                          body={'registration_id': registration_id, 'code': code})
        return _persist_login(endpoint, tokens)


def resend_confirmation(registration_id, *, endpoint=DEFAULT_ENDPOINT):
    import uuid
    return _request(endpoint, '/auth/resend-email', method='POST',
                    body={'registration_id': str(uuid.UUID(registration_id))})


def request(path, *, method='GET', body=None, raw=None, binary=False):
    with _lock:
        saved = _read()
        if not saved:
            raise CloudError('invalid_session', 401)

        def refresh():
            try:
                tokens = _request(saved['endpoint'], '/auth/refresh', method='POST', body={'refresh_token': saved['refresh_token']})
            except CloudError as exc:
                if exc.status == 401:
                    _save(None)
                raise
            saved.update(tokens, expires_at=time.time() + tokens['expires_in'])
            _save(saved)  # Persist rotation before any subsequent request.

        if saved['expires_at'] < time.time() + 30:
            refresh()
        try:
            return _request(saved['endpoint'], path, method=method, body=body, token=saved['access_token'], raw=raw, binary=binary)
        except CloudError as exc:
            if exc.status != 401:
                raise
            refresh()
            return _request(saved['endpoint'], path, method=method, body=body, token=saved['access_token'], raw=raw, binary=binary)


def sign_out(*, local_only=False):
    with _lock:
        if not _read():
            return
        if not local_only:
            # Connection failure leaves the session available for a safe retry.
            # Offline removal is a separate explicit UI action and says that the
            # server session remains active until revoked or expired.
            try:
                request('/auth/logout', method='POST')
            except CloudError as exc:
                if exc.status != 401:
                    raise
        _save(None)


def sessions():
    rows=request('/sessions')['sessions']
    for row in rows:
        if row.get('current') and row['device_name'].casefold() in ('localhost','android','unknown'):
            name=_device()
            if name.casefold() not in ('localhost','android','unknown'):
                try:rename_session(row['id'],name);row['device_name']=name
                except CloudError:pass
    return rows


def rename_session(identifier,name):
    import uuid
    identifier=str(uuid.UUID(identifier));name=(name or '').strip()
    if not 1<=len(name)<=120 or any(ord(c)<32 for c in name):raise ValueError('Введите название устройства до 120 символов')
    result=request('/sessions/'+identifier,method='PUT',body={'device_name':name})
    with _lock:
        saved=_read()
        if saved and saved.get('session_id')==identifier:saved['device_name']=name;_save(saved)
    return result


def revoke_session(identifier):
    import uuid
    identifier = str(uuid.UUID(identifier))
    current = state()
    result = request('/sessions/' + identifier, method='DELETE')
    if current and identifier == current['session_id']:
        with _lock:
            _save(None)
    return result
