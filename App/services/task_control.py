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
    def __init__(self, task): self.task = task; self.paused_cancel = False
    def is_set(self):
        paused=self.task.paused
        self.paused_cancel=self.paused_cancel or paused
        return self.task.cancelled.is_set() or paused


class TaskControl:
    def __init__(self, cancelled=None, on_state=None):
        self.id = uuid.uuid4().hex
        self.cancelled = cancelled or threading.Event()
        self._manual = False
        self._offline = False
        self._condition = threading.Condition()
        self.on_state = on_state
        self.probe = None
        self.signal = _GenerationSignal(self)

    @property
    def paused(self):
        with self._condition: return self._manual or self._offline

    @property
    def state(self):
        with self._condition:
            if self.cancelled.is_set(): return 'Остановлено'
            if self._manual: return 'На паузе'
            if self._offline: return 'Нет соединения · продолжу автоматически'
            return 'Выполняется'

    def _notify(self):
        if self.on_state: self.on_state(self.state)

    def pause(self):
        with self._condition: self._manual = True; self._condition.notify_all()
        self._notify()

    def resume(self):
        with self._condition: self._manual = False; self._condition.notify_all()
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

    def generate(self, function, prompt, *, network=False, probe=None, **kwargs):
        """Пауза отменяет текущую генерацию. После возобновления повторяется
        только незавершённый шаг модели; выполненные инструменты не повторяются.
        Провайдер может тарифицировать отменённый запрос.
        """
        probe = probe or (probe_api if network else None)
        self.probe = probe
        while True:
            self.checkpoint(probe)
            signal=_GenerationSignal(self)
            try:
                result = function(prompt, cancelled=signal, **kwargs)
                self.checkpoint(probe)
                return result
            except CancelledError:
                if self.cancelled.is_set() or (not signal.paused_cancel and not self.paused): raise
                # User pause interrupted inference, not the whole task.
            except Exception as exc:
                if self.cancelled.is_set(): raise CancelledError() from exc
                if self.paused: continue
                if not network or not network_error(exc): raise
                self.connection(False)
