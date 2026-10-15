"""
Файл: /App/services/remote_tasks.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Зашифрованные задания телефон → ПК, явный список разрешённых отправителей,
          отдельные подтверждения записи файлов и команд, отмена и результаты.
"""
import json
import hashlib
import threading
import time
import uuid
from concurrent.futures import CancelledError
from . import cloud_account as cloud, cloud_sync, workspaces
from .db import get_db
from .sync_crypto import b64, unb64, seal, open_sealed, canonical
from .platforms import is_android

_thread = None
_stop = threading.Event()
_active = threading.Event()
_cancel = None
_state = {'running': False, 'error': '', 'progress': ''}
_guard = lambda: True


class DeliveryPending(RuntimeError):
    def __init__(self,identifier):
        self.identifier=identifier
        super().__init__('Соединение прервалось. Проверьте доставку: повтор использует то же задание и не создаёт копию.')


def credentials():
    account = cloud.state()
    if not account: raise ValueError('Сначала войдите в аккаунт Xopilot')
    key = get_db().get_setting('cloud_sync_key:'+account['account_id'])
    if not key: raise ValueError('Введите пароль сквозной синхронизации на обоих устройствах')
    return account, unb64(key)


def encode(identifier, kind, value):
    account, key = credentials()
    return b64(seal(key, account['account_id'], 'remote:'+kind+':'+str(identifier), canonical(value)))


def decode(identifier, kind, value):
    account, key = credentials()
    return json.loads(open_sealed(key, account['account_id'], 'remote:'+kind+':'+str(identifier), unb64(value), max_bytes=512*1024))


def options():
    account = cloud.state()
    return json.loads(get_db().get_setting('remote_host:'+account['account_id']) or '{"enabled":false,"senders":[]}') if account else {'enabled': False, 'senders': []}


def configure(enabled, senders, *, guard=None):
    if is_android() and enabled: raise ValueError('Принимать задания может приложение на ПК')
    account, _ = credentials()
    value = {'enabled': bool(enabled), 'senders': list(dict.fromkeys(senders))}
    cloud.request('/remote/hosts', method='PUT', body=value)
    get_db().set_setting('remote_host:'+account['account_id'], json.dumps(value))
    if enabled: start(guard=guard)
    else:
        _stop.set()
        if _cancel is not None: _cancel.set()
    return value


def hosts():
    credentials()
    try:return cloud.request('/remote/hosts')['hosts']
    except cloud.CloudError as exc:
        if exc.status==404:raise ValueError('На сервере пока недоступно подключение к ПК. Требуется обновление серверной части Xopilot.') from None
        raise


def submit(target, prompt, workspace_id='all'):
    account, _ = credentials()
    if not str(prompt).strip(): raise ValueError('Введите задание для ПК')
    identifier = str(uuid.uuid4())
    task = {'version': 1, 'id': identifier, 'sender': account['session_id'], 'target': target,
            'prompt': str(prompt), 'workspace_id': workspace_id}
    # Keep this immutable operation for a user-triggered retry after a lost reply.
    pending_key = 'remote_pending:'+identifier
    body = {'id': identifier, 'target': target, 'task': encode(identifier, 'task', task)}
    get_db().set_setting(pending_key, json.dumps(body))
    ids = json.loads(get_db().get_setting('remote_jobs:'+account['account_id']) or '[]')
    ids.append(identifier); get_db().set_setting('remote_jobs:'+account['account_id'], json.dumps(ids))
    try:cloud.request('/remote/jobs', method='POST', body=body)
    except cloud.CloudError as exc:
        if exc.code=='connection_failed' or exc.status>=500:raise DeliveryPending(identifier) from None
        raise
    get_db().set_setting(pending_key, '')
    return identifier


def retry(identifier):
    value = get_db().get_setting('remote_pending:'+identifier)
    if not value: raise ValueError('Нет неотправленного задания')
    cloud.request('/remote/jobs', method='POST', body=json.loads(value))
    get_db().set_setting('remote_pending:'+identifier, '')


def inspect(identifier):
    row = cloud.request('/remote/jobs/'+identifier)
    if row.get('result'): row['decoded_result'] = decode(identifier, 'result', row['result'])
    return row


def decide(identifier, question, request, approved):
    digest = hashlib.sha256(canonical(request)).hexdigest()
    value = {'question': question, 'request_hash': digest, 'approved': bool(approved)}
    cloud.request('/remote/jobs/'+identifier+'/decision', method='POST',
        body={'question': question, 'decision': encode(identifier, 'decision:'+question, value)})


def cancel(identifier):
    cloud.request('/remote/jobs/'+identifier, method='DELETE')
    get_db().set_setting('remote_pending:'+identifier,'')


def pending_deliveries():
    account,_=credentials()
    identifiers=json.loads(get_db().get_setting('remote_jobs:'+account['account_id']) or '[]')
    return [identifier for identifier in identifiers if get_db().get_setting('remote_pending:'+identifier)]
def running(): return _active.is_set()
def status(): return dict(_state)


def _result(identifier, state, value, question=None):
    cloud.request('/remote/jobs/'+identifier+'/result', method='PUT',
        body={'state': state, 'result': encode(identifier, 'result', value), 'question': question})


def _approve(identifier, request, cancelled):
    question = str(uuid.uuid4())
    digest = hashlib.sha256(canonical(request)).hexdigest()
    _result(identifier, 'approval', {'request': request, 'question': question}, question)
    while not cancelled.wait(2):
        row = inspect(identifier)
        if row['state'] in {'cancelled', 'expired'}: cancelled.set(); return False
        if row.get('question') != question: raise ValueError('Запрос подтверждения изменился')
        if row.get('decision'):
            decision = decode(identifier, 'decision:'+question, row['decision'])
            if decision.get('question') != question or decision.get('request_hash') != digest:
                raise ValueError('Подтверждение относится к другому действию')
            approved = decision.get('approved') is True
            _result(identifier, 'running', {'progress': 'Действие подтверждено' if approved else 'Действие отклонено'})
            return approved
    return False


def _execute(row, cancelled):
    from . import agent, chat_store, api_chat, llm, model_settings
    account, _ = credentials()
    task = decode(row['id'], 'task', row['task'])
    if task.get('id') != row['id'] or task.get('target') != account['session_id'] or task.get('sender') != row['sender']:
        raise ValueError('Адресат или отправитель зашифрованного задания не совпадает')
    if task.get('version') != 1 or not isinstance(task.get('prompt'), str): raise ValueError('Неверный формат задания')
    workspace = task.get('workspace_id', 'all')
    if workspace not in {item['id'] for item in workspaces.list_workspaces()}:
        raise ValueError('Пространство ещё не синхронизировано с ПК')
    # Do not switch the user's visible chat or overwrite an unfinished draft.
    cid = get_db().create_chat('Задание с телефона')
    workspaces.assign_chat(cid, workspace)
    chat_store.save_user_message(cid, task['prompt'])
    instructions, files = workspaces.chat_resources(cid)
    if api_chat.is_api_selected(): generate = api_chat.generate_reply
    else:
        chosen = model_settings.get_selected_chat_model()
        if not chosen: raise ValueError('На ПК выберите API или установленную локальную модель')
        llm.ensure_model_loaded(chosen); generate = llm.generate_reply
    def progress(value):
        _state['progress'] = value
        if cancelled.is_set(): raise CancelledError()
        _result(row['id'], 'running', {'progress': value})
    reply = agent.run_agent(task['prompt'], chat_id=cid, history=[], attachments=files, instructions=instructions,
        level='auto', cancelled=cancelled, generate=generate, on_progress=progress,
        approve=lambda request: _approve(row['id'], request, cancelled), request_id='remote:'+row['id'])
    chat_store.save_ai_message(cid, reply, attachments=reply.files)
    _result(row['id'], 'completed', {'reply': str(reply), 'files': [name for name, _ in reply.files], 'workspace_id': workspace})
    # Deliver the generated chat/files using the existing E2EE replication path.
    if cloud_sync.options()['enabled']: cloud_sync.run()


def start(*, guard=None):
    global _thread, _guard
    if is_android(): return
    if guard is not None: _guard = guard
    if _thread is not None and _thread.is_alive(): return
    if not options().get('enabled'): return
    credentials(); _stop.clear()
    def loop():
        global _cancel
        original = cloud.state()['account_id']
        while not _stop.is_set():
            try:
                account = cloud.state()
                if not account or account['account_id'] != original or not options()['enabled']: break
                rows = cloud.request('/remote/inbox')['jobs']
                if rows and _guard():
                    row = rows[0]; cancelled = _cancel = threading.Event()
                    cloud.request('/remote/jobs/'+row['id']+'/claim', method='POST', body={})
                    _active.set(); _state.update(running=True, error='')
                    monitor_stop = threading.Event()
                    def monitor():
                        while not monitor_stop.wait(2):
                            try:
                                current = cloud.state()
                                if not current or current['account_id'] != original or inspect(row['id'])['state'] in {'cancelled','expired'}:
                                    cancelled.set(); break
                            except Exception:
                                cancelled.set(); break  # No command after lost authorization/network state.
                    watcher = threading.Thread(target=monitor, daemon=True, name='RemoteCancellation'); watcher.start()
                    try: _execute(row, cancelled)
                    except CancelledError:
                        try:cancel(row['id'])
                        except Exception:pass  # Offline cancellation can still be requested from the phone.
                    except Exception as exc:
                        _state['error'] = str(exc)
                        try: _result(row['id'], 'failed', {'error': str(exc)})
                        except Exception: pass
                    finally:
                        monitor_stop.set(); _active.clear(); _state['running'] = False; _cancel = None
                # Keep the last failure visible until a new task starts.
            except Exception as exc: _state['error'] = str(exc)
            _stop.wait(10)
    _thread = threading.Thread(target=loop, daemon=True, name='RemoteTasks'); _thread.start()


def shutdown():
    """Cancel an active task and stop polling when this application closes."""
    _stop.set()
    if _cancel is not None:_cancel.set()
    if _thread is not None and _thread is not threading.current_thread():_thread.join(timeout=5)
