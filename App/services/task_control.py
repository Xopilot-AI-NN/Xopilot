"""
Файл: /App/services/task_control.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Пауза, отмена и восстановление генерации без повторения действий.
"""
from concurrent.futures import CancelledError
import errno
import http.client
import socket
import ssl
import threading
import uuid
from urllib.parse import urlsplit


class RateLimitedError(RuntimeError):
    """Provider quota exhausted: pause one model step without replaying tools."""


class EmptyModelReplyError(RuntimeError):
    """A provider response with no usable assistant content."""


def network_error(error):
    current = error
    while current:
        if isinstance(current,OSError) and current.errno in {errno.ENETDOWN,errno.ENETUNREACH,errno.EHOSTUNREACH,errno.ECONNRESET,errno.ECONNREFUSED,errno.ETIMEDOUT}:return True
        if isinstance(current, (ConnectionError, TimeoutError, socket.gaierror,
                                http.client.RemoteDisconnected, http.client.IncompleteRead)):
            return True
        current = current.__cause__ or current.__context__
    return False


def probe_api():
    """Проверка TLS без передачи ключа, запроса пользователя или истории."""
    from .api_chat import configuration
    url = urlsplit(configuration()['url'])
    with socket.create_connection((url.hostname, url.port or (443 if url.scheme == 'https' else 80)), timeout=3) as sock:
        if url.scheme == 'https':
            with ssl.create_default_context().wrap_socket(sock, server_hostname=url.hostname):
                pass
    return True


class _GenerationSignal:
    def __init__(self, task, revision=None):
        self.task = task; self.paused_cancel = False
        self.revision = task.revision if revision is None else revision
    def is_set(self):
        paused=self.task.paused
        changed=self.revision != self.task.revision
        self.paused_cancel=self.paused_cancel or paused or changed
        return self.task.cancelled.is_set() or paused or changed


class TaskControl:
    def __init__(self, cancelled=None, on_state=None):
        self.id = uuid.uuid4().hex
        self.cancelled = cancelled or threading.Event()
        self._manual = False
        self._pause_reason = ''
        self._offline = False
        self._condition = threading.Condition()
        self._revision = 0
        self._updates = []
        self._instructions = []
        self.on_state = on_state
        self.probe = None
        self.signal = _GenerationSignal(self)

    @property
    def revision(self):
        with self._condition: return self._revision

    def add_instruction(self, text, attachments=(), message_id=None):
        with self._condition:
            update={'text': text, 'attachments': list(attachments), 'message_id':message_id}
            self._updates.append(update);self._instructions.append(update)
            self._revision += 1
            self._manual = False
            self._pause_reason = ''
            self._condition.notify_all()
        self._notify()

    def _take_updates(self):
        with self._condition:
            updates,self._updates=self._updates,[]
            return updates,self._revision

    def instruction_snapshot(self):
        with self._condition:return list(self._instructions)

    def take_pending_instructions(self):
        return self._take_updates()[0]

    @property
    def paused(self):
        with self._condition: return self._manual or self._offline

    @property
    def state(self):
        with self._condition:
            if self.cancelled.is_set(): return 'Остановлено'
            if self._manual: return self._pause_reason or 'На паузе'
            if self._offline: return 'Нет соединения · продолжу автоматически'
            return 'Выполняется'

    def _notify(self):
        if self.on_state: self.on_state(self.state)

    def pause(self, reason=''):
        with self._condition: self._manual = True; self._pause_reason = reason; self._condition.notify_all()
        self._notify()

    def resume(self):
        with self._condition: self._manual = False; self._pause_reason = ''; self._condition.notify_all()
        self._notify()

    def connection(self, available):
        with self._condition: self._offline = not available; self._condition.notify_all()
        self._notify()

    def cancel(self):
        self.cancelled.set()
        with self._condition: self._condition.notify_all()
        self._notify()

    def checkpoint(self, probe=None):
        probe = probe or self.probe
        while True:
            with self._condition:
                if self.cancelled.is_set(): raise CancelledError()
                if not (self._manual or self._offline): return
                offline = self._offline
                self._condition.wait(timeout=3 if offline else .1)
            if offline and probe:
                try:
                    if probe(): self.connection(True)
                except (OSError, ValueError, RuntimeError): pass

    def generate(self, function, prompt, *, network=False, probe=None, on_updates=None, **kwargs):
        """Пауза отменяет текущую генерацию. После возобновления повторяется
        только незавершённый шаг модели; выполненные инструменты не повторяются.
        Провайдер может тарифицировать отменённый запрос.
        """
        probe = probe or (probe_api if network else None)
        self.probe = probe
        empty_retries = 0
        while True:
            self.checkpoint(probe)
            updates,revision=self._take_updates()
            if updates:
                if on_updates:
                    prompt,kwargs=on_updates(updates,kwargs)
                else:
                    prompt += '\n\nУточнения пользователя к текущей задаче:\n' + '\n'.join(u['text'] for u in updates)
                    kwargs['attachments']=list(dict.fromkeys([*(kwargs.get('attachments') or []),
                        *(file for update in updates for file in update['attachments'])]))
            signal=_GenerationSignal(self,revision)
            try:
                result = function(prompt, cancelled=signal, **kwargs)
                self.checkpoint(probe)
                if signal.revision != self.revision: continue
                return result
            except CancelledError:
                if self.cancelled.is_set() or (not signal.paused_cancel and not self.paused and signal.revision==self.revision): raise
                # User pause interrupted inference, not the whole task.
            except Exception as exc:
                if self.cancelled.is_set(): raise CancelledError() from exc
                if self.paused: continue
                if network and isinstance(exc,EmptyModelReplyError):
                    if not empty_retries:
                        empty_retries=1
                        continue  # Only repeat the unfinished model step, never tools.
                    empty_retries=0
                    self.pause('Модель вернула пустой ответ · нажмите продолжить')
                    continue
                if network and isinstance(exc,RateLimitedError):
                    self.pause('Лимит API · продолжите позже или смените модель')
                    continue
                if not network or not network_error(exc): raise
                self.connection(False)
