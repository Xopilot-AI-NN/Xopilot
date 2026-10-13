"""Owner-only OAuth setup. Run on a PC; transfer the resulting file to the server.

Secrets never enter command-line arguments or application packages. This tool
creates tokens only; it does not enable billing or create payments.
"""
import argparse
import getpass
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
import webbrowser

SCOPES = 'oauth-user-show oauth-donation-index'
REDIRECT = 'http://127.0.0.1:8766/callback'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def authorization_url(client_id, redirect_uri, state):
    if not client_id.isascii() or not client_id.isdigit() or len(client_id) > 32:
        raise ValueError('Client ID должен быть числом из DonationAlerts')
    return 'https://www.donationalerts.com/oauth/authorize?' + urlencode({
        'client_id':client_id, 'redirect_uri':redirect_uri, 'response_type':'code',
        'scope':SCOPES, 'state':state})


def callback_code(target, expected_path, state):
    parts = urlsplit(target)
    if parts.path != expected_path or parts.fragment: raise ValueError('Неверный callback')
    query = parse_qs(parts.query, strict_parsing=True)
    if len(query.get('state', [])) != 1 or not secrets.compare_digest(query['state'][0], state):
        raise ValueError('Неверный state: запрос не относится к этому подключению')
    if query.get('error'): raise ValueError('Владелец не разрешил подключение DonationAlerts')
    codes = query.get('code', [])
    if len(codes) != 1 or not 1 <= len(codes[0]) <= 4096: raise ValueError('Отсутствует код авторизации')
    return codes[0]


def read_json(response):
    with response:
        raw = response.read(512*1024+1)
    if len(raw) > 512*1024: raise ValueError('Слишком большой ответ DonationAlerts')
    result = json.loads(raw)
    if not isinstance(result, dict): raise ValueError('Неверный ответ DonationAlerts')
    return result


def exchange(client_id, client_secret, redirect_uri, code, recipient, opener=None):
    opener = opener or build_opener(NoRedirect())
    data = urlencode({'grant_type':'authorization_code', 'client_id':client_id,
        'client_secret':client_secret, 'redirect_uri':redirect_uri, 'code':code}).encode()
    token = read_json(opener.open(Request('https://www.donationalerts.com/oauth/token', data=data,
        headers={'Content-Type':'application/x-www-form-urlencoded', 'User-Agent':'Xopilot-Owner-Setup/1'}), timeout=20))
    access, refresh, duration = token.get('access_token'), token.get('refresh_token'), token.get('expires_in')
    if (not isinstance(access,str) or not 1 <= len(access) <= 16384 or
            not isinstance(refresh,str) or not 1 <= len(refresh) <= 16384 or
            type(duration) is not int or not 120 < duration <= 3153600000):
        raise ValueError('DonationAlerts не вернул полноценную пару токенов')
    account = read_json(opener.open(Request('https://www.donationalerts.com/api/v1/user/oauth',
        headers={'Authorization':'Bearer '+access, 'User-Agent':'Xopilot-Owner-Setup/1'}), timeout=20))
    if account.get('data',{}).get('code') != recipient:
        raise ValueError('Авторизован другой получатель. Подключите владельца страницы '+recipient)
    # Verify donation-read scope before saving a token that cannot reconcile orders.
    read_json(opener.open(Request('https://www.donationalerts.com/api/v1/alerts/donations?page=1',
        headers={'Authorization':'Bearer '+access, 'User-Agent':'Xopilot-Owner-Setup/1'}), timeout=20))
    return {'access_token':access, 'refresh_token':refresh, 'expires_at':int(time.time())+duration}


def write_tokens(path, tokens):
    path = Path(path).expanduser()
    payload = json.dumps(tokens)
    if len(payload.encode()) > 32768: raise ValueError('Пара токенов превышает допустимый размер файла')
    if not path.parent.is_dir(): raise ValueError('Сначала создайте защищённый каталог для токенов')
    if os.name == 'posix' and path.parent.stat().st_mode & 0o077:
        raise ValueError('Каталог токенов должен иметь права 700')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, 'O_NOFOLLOW'): flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def receive_code(state, port, timeout=600, on_ready=lambda:None):
    result = {}
    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *_): pass  # Callback URL contains a one-time secret.
        def do_GET(self):
            try:
                code = callback_code(self.path, '/callback', state)
            except ValueError:
                self.send_response(400)
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(b'Invalid OAuth callback. Return to the setup tool.')
                return
            result['code'] = code
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write('Ответ получен. Вернитесь к консоли Xopilot. Эту вкладку можно закрыть.'.encode())
    with HTTPServer(('127.0.0.1', port), Callback) as server:
        server.timeout = 1
        on_ready()
        deadline = time.monotonic()+timeout
        while 'code' not in result and time.monotonic() < deadline:
            server.handle_request()
    if 'code' not in result: raise ValueError('Ожидание авторизации истекло. Запустите подключение заново.')
    return result['code']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client-id', required=True)
    parser.add_argument('--recipient', default='denbroliik')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--port', default=8766, type=int)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if args.output.expanduser().exists(): parser.error('Файл уже существует. Используйте новый путь: старые токены не перезаписываются.')
    if not 1024 <= args.port <= 65535: parser.error('Порт: 1024–65535')
    if not args.recipient or not all(c.isascii() and (c.isalnum() or c in '_-') for c in args.recipient):
        parser.error('Неверное имя страницы получателя')
    state = secrets.token_urlsafe(32)
    redirect = f'http://127.0.0.1:{args.port}/callback'
    url = authorization_url(args.client_id, redirect, state)
    print('Redirect URI в DonationAlerts должен точно совпадать:', redirect)
    secret = getpass.getpass('Client secret DonationAlerts (ввод скрыт): ').strip()
    if not secret: parser.error('Нужен Client secret')
    def ready():
        print('Войдите владельцем страницы', args.recipient, 'и подтвердите подключение:\n'+url)
        if not args.no_browser: webbrowser.open(url)
    code = receive_code(state, args.port, on_ready=ready)
    tokens = exchange(args.client_id, secret, redirect, code, args.recipient)
    write_tokens(args.output, tokens)
    print('Токены сохранены в', args.output.expanduser(), '\nОплата не включена. Перенесите файл на сервер по SSH и настройте billing.env.')


if __name__ == '__main__':
    try: main()
    except (Exception, KeyboardInterrupt) as exc:
        # Provider errors can contain request/token data: never print their body.
        print('Подключение не завершено ('+type(exc).__name__+'). Проверьте Redirect URI, аккаунт и доступность DonationAlerts.')
        raise SystemExit(1)
