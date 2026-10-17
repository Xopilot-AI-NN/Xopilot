"""
Файл: App/services/model_installer.py
Описание: Установка официальной LiteRT-LM модели Gemma 4 E2B для Xopilot.

Скачивание потоковое: модель не держится целиком в памяти. После загрузки
проверяется SHA-256, затем временный .part атомарно заменяет целевой файл.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import json
import re
import socket
import threading
import time
import urllib.error
import http.client
from pathlib import Path
import urllib.request

from .llm import DEFAULT_FILENAME, MODELS_DIR, get_model_path


@dataclass(frozen=True)
class DownloadableModel:
    id: str
    name: str
    filename: str
    description: str
    size_label: str
    source: str
    download_url: str
    sha256: str

    @property
    def path(self) -> Path:
        return Path(MODELS_DIR) / self.filename

    @property
    def installed(self) -> bool:
        return Path(get_model_path(self.filename)).is_file()


GEMMA_4_E2B = DownloadableModel(
    id="gemma-4-e2b",
    name="Gemma4-e2b",
    filename=DEFAULT_FILENAME,
    description="Основная мультимодальная LiteRT-LM модель Xopilot для чата и Live.",
    size_label="~2.59 GB",
    source="litert-community/gemma-4-E2B-it-litert-lm",
    download_url=(
        "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/"
        "gemma-4-E2B-it.litertlm?download=true"
    ),
    sha256="181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c",
)

GEMMA_4_E4B = DownloadableModel(
    id='gemma-4-e4b', name='Gemma4-e4b', filename='gemma-4-E4B-it.litertlm',
    description='Мультимодальная LiteRT-LM модель для чата и Live.', size_label='~3.66 GB',
    source='litert-community/gemma-4-E4B-it-litert-lm',
    download_url='https://huggingface.co/litert-community/gemma-4-E4B-it-litert-lm/resolve/main/gemma-4-E4B-it.litertlm?download=true',
    sha256='0b2a8980ce155fd97673d8e820b4d29d9c7d99b8fa6806f425d969b145bd52e0')
DOWNLOADABLE_MODELS = {model.id: model for model in (GEMMA_4_E2B, GEMMA_4_E4B)}


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def import_model(name, *, path=None, data=None):
    """Import a catalog model from SAF/USB without buffering it in memory."""
    import shutil
    from filelock import FileLock
    model=next((m for m in DOWNLOADABLE_MODELS.values() if m.filename==name),None)
    if model is None or not path or data is not None:
        raise ValueError('Выберите оригинальный .litertlm файл Gemma из каталога')
    source=Path(path)
    if not source.is_file():raise ValueError('Исходный файл недоступен')
    model.path.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(model.path.parent).free<source.stat().st_size+64*1024**2:
        raise ValueError('Недостаточно места для импорта модели')
    with FileLock(str(partial_path(model))+'.lock',timeout=0):
        temporary=model.path.with_suffix('.importing')
        try:
            shutil.copyfile(source,temporary)
            if _digest_file(temporary)!=model.sha256:
                raise ValueError('SHA-256 не совпадает: файл повреждён или это другая модель')
            os.replace(temporary,model.path)
        finally:temporary.unlink(missing_ok=True)
    return str(model.path)


class DownloadPaused(Exception):
    """The verified partial download is retained for continuation."""


class DownloadInterrupted(Exception):
    """A network interruption leaves the partial file intact."""


def partial_path(model):
    return model.path.with_name(model.path.name + '.part')


def install_model(model_id=GEMMA_4_E2B.id, *, progress=None, pause=None):
    """Stream, resume with Range/If-Range, verify SHA-256 and replace atomically."""
    from filelock import FileLock
    model = DOWNLOADABLE_MODELS[model_id]
    model.path.parent.mkdir(parents=True, exist_ok=True)
    temporary = partial_path(model)
    metadata = temporary.with_suffix(temporary.suffix + '.json')
    with FileLock(str(temporary) + '.lock', timeout=0):
        identity = {'url': model.download_url, 'sha256': model.sha256}
        try:
            saved = json.loads(metadata.read_text())
        except (OSError, ValueError):
            saved = {}
        if any(saved.get(k) != v for k, v in identity.items()):
            temporary.unlink(missing_ok=True)
            saved = identity
        offset = temporary.stat().st_size if temporary.exists() else 0
        total = saved.get('total')
        last_notice = 0
        def check_pause():
            if pause is not None and pause.is_set():
                raise DownloadPaused()
        def notify(state, force=False):
            nonlocal last_notice
            now = time.monotonic()
            if progress and (force or now - last_notice >= .25):
                progress(offset, total, state)
                last_notice = now
        check_pause()
        headers = {'User-Agent': 'Xopilot-Model-Installer/2.0', 'Accept-Encoding': 'identity'}
        if offset:
            headers['Range'] = f'bytes={offset}-'
            if saved.get('validator'):
                headers['If-Range'] = saved['validator']
        notify('downloading', True)
        try:
            request = urllib.request.Request(model.download_url, headers=headers)
            try:
                response = urllib.request.urlopen(request, timeout=15)
            except urllib.error.HTTPError as exc:
                if exc.code == 416 and offset and exc.headers.get('Content-Range') == f'bytes */{offset}':
                    response = None  # Complete partial file: still verify its digest.
                    total = offset
                else:
                    if exc.code >= 500 or exc.code in (408, 429):
                        raise DownloadInterrupted(f'Сервер временно недоступен (HTTP {exc.code})') from exc
                    raise RuntimeError(f'Не удалось скачать модель: HTTP {exc.code}') from exc
            if response is not None:
                with response:
                    status = response.status
                    if status == 206:
                        match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                        if not match or int(match[1]) != offset:
                            raise RuntimeError('Сервер вернул неверный диапазон файла. Загрузка остановлена.')
                        total = int(match[3])
                    elif status == 200:
                        # Server ignored Range or changed the entity: restart safely.
                        offset = 0
                        length = response.headers.get('Content-Length')
                        total = int(length) if length and length.isdecimal() else None
                    else:
                        raise RuntimeError(f'Сервер модели вернул HTTP {status}')
                    saved = {**identity, 'total': total,
                             'validator': response.headers.get('ETag') or response.headers.get('Last-Modified')}
                    metadata.write_text(json.dumps(saved))
                    with temporary.open('ab' if offset else 'wb') as output:
                        while True:
                            check_pause()
                            chunk = response.read(256 * 1024)
                            if not chunk:
                                break
                            output.write(chunk)
                            offset += len(chunk)
                            notify('downloading')
                    if total is not None and offset != total:
                        raise DownloadInterrupted('Соединение оборвалось до конца файла')
        except (urllib.error.URLError, socket.timeout, ConnectionError, http.client.HTTPException) as exc:
            check_pause()
            raise DownloadInterrupted('Нет соединения. Загруженная часть сохранена.') from exc
        check_pause()
        notify('verifying', True)
        digest = hashlib.sha256()
        with temporary.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                check_pause()
                digest.update(chunk)
        if digest.hexdigest() != model.sha256:
            temporary.unlink(missing_ok=True)
            metadata.unlink(missing_ok=True)
            raise RuntimeError(f'SHA-256 {model.name} не совпал. Повреждённая загрузка удалена; попробуйте снова.')
        os.replace(temporary, model.path)
        metadata.unlink(missing_ok=True)
        notify('installed', True)
        return model.path


class ModelDownload:
    """One shared background job per model, independent of an open dialog."""
    def __init__(self, model_id):
        self.model_id = model_id
        self.pause_requested = threading.Event()
        self.worker = None
        self.state = 'paused' if partial_path(DOWNLOADABLE_MODELS[model_id]).exists() else 'idle'
        self.downloaded = partial_path(DOWNLOADABLE_MODELS[model_id]).stat().st_size if self.state == 'paused' else 0
        self.total = None
        self.error = ''
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self.worker is not None and self.worker.is_alive():
                return
            self.pause_requested.clear()
            self.state, self.error = 'downloading', ''
            self.worker = threading.Thread(target=self._run, daemon=True)
            self.worker.start()

    def pause(self):
        self.pause_requested.set()
        if self.state == 'waiting':
            self.state = 'paused'

    def _progress(self, downloaded, total, state):
        self.downloaded, self.total, self.state = downloaded, total, state

    def _run(self):
        try:
            while True:
                try:
                    install_model(self.model_id, progress=self._progress, pause=self.pause_requested)
                    self.state = 'installed'
                    return
                except DownloadInterrupted as exc:
                    self.state, self.error = 'waiting', str(exc)
                    if self.pause_requested.wait(5):
                        raise DownloadPaused()
        except DownloadPaused:
            self.state = 'paused'
        except Exception as exc:
            self.state, self.error = 'error', str(exc)


_DOWNLOADS = {}
_DOWNLOADS_LOCK = threading.Lock()


def model_download(model_id):
    with _DOWNLOADS_LOCK:
        if model_id not in _DOWNLOADS:
            _DOWNLOADS[model_id] = ModelDownload(model_id)
        return _DOWNLOADS[model_id]
