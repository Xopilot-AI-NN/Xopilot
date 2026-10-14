"""
Файл: /App/services/task_processes.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Отслеживаемые фоновые процессы проектов и их завершение.
"""
from collections import deque
from concurrent.futures import CancelledError
import os
import signal
import subprocess
import threading
import time
import uuid

_lock = threading.RLock()
_processes = {}


class Process:
    def __init__(self, owner, workspace, argv, cwd):
        self.id = uuid.uuid4().hex
        self.owner, self.workspace, self.argv, self.cwd = owner, workspace, list(argv), str(cwd)
        self.output = deque(maxlen=32)
        self.started = time.time()
        options = {'start_new_session': True} if os.name != 'nt' else {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
        self.process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **options)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        try:
            while chunk := self.process.stdout.read1(4096):
                with _lock: self.output.append(chunk)
        finally: self.process.stdout.close()

    def snapshot(self):
        with _lock:
            code = self.process.poll()
            return {'id': self.id, 'workspace': self.workspace, 'argv': self.argv,
                    'cwd': self.cwd, 'pid': self.process.pid, 'running': code is None,
                    'exit_code': code, 'output': b''.join(self.output).decode('utf-8', errors='replace'),
                    'started': self.started}

    def stop(self):
        if self.process.poll() is not None and not self.reader.is_alive():return self.snapshot()
        if os.name == 'nt':
            if self.process.poll() is None:
                subprocess.run(['taskkill','/T','/F','/PID',str(self.process.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        else:
            # A child can outlive its original parent; always stop the group.
            try: os.killpg(self.process.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try: self.process.wait(timeout=2)
            except subprocess.TimeoutExpired: pass
            try: os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        self.process.wait(timeout=5)
        self.reader.join(timeout=2)
        return self.snapshot()


def start(owner, workspace, argv, cwd):
    with _lock:
        # Bound simultaneous OS processes, not the number of agent actions.
        if sum(item.process.poll() is None for item in _processes.values()) >= 8:
            raise ValueError('Уже работают 8 процессов. Завершите ненужный процесс перед новым запуском.')
        item = Process(owner, workspace, argv, cwd)
        _processes[item.id] = item
        # Retain a bounded journal after short commands have finished.
        finished = [key for key, value in _processes.items() if value.process.poll() is not None]
        for key in finished[:-100]: _processes.pop(key, None)
        return item.snapshot()


def get(identifier, owner, workspace):
    with _lock: item = _processes.get(identifier)
    if not item or item.owner != owner or item.workspace != workspace:
        raise ValueError('Процесс этой задачи не найден')
    return item


def snapshots(owner=None,workspace=None):
    with _lock: return [item.snapshot() for item in _processes.values()
        if (owner is None or item.owner==owner) and (workspace is None or item.workspace==workspace)]


def stop_all(owner=None):
    with _lock: items = [p for p in _processes.values() if owner is None or p.owner == owner]
    for item in items: item.stop()


def wait(identifier, owner, workspace, cancelled, timeout=600):
    item = get(identifier, owner, workspace)
    deadline = time.monotonic()+timeout
    try:
        while item.process.poll() is None:
            if cancelled.wait(.1): raise CancelledError()
            if time.monotonic() > deadline: raise TimeoutError('Команда превысила 10 минут; для сервера используйте фоновый процесс')
    except BaseException:
        item.stop()
        raise
    item.reader.join(timeout=2)
    return item.snapshot()


def stop_process(identifier):
    with _lock:item=_processes.get(identifier)
    if not item:raise ValueError('Процесс не найден')
    return item.stop()


def has_processes():
    with _lock:return bool(_processes)

def has_running():
    with _lock:return any(item.process.poll() is None for item in _processes.values())
