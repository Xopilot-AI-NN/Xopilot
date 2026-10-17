"""
Файл: App/services/voice_installer.py
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: Установка Piper-моделей и обученного тембра Miku для голосов Live.

Её используют и интерфейс настроек, и scripts/install_russian_voice.py.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
import urllib.request
from dataclasses import dataclass
from concurrent.futures import CancelledError

from .voice_catalog import MODELS, REVISION, VOICES, VOICE_DIR


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class DownloadProgress:
    name: str
    downloaded: int
    total: int | None
    phase: str = 'download'


def download_verified(url: str, target: Path, expected_hash: str, *, on_download=None, cancelled=None) -> None:
    def check():
        if cancelled is not None and cancelled.is_set():raise CancelledError()
    def report(count, total, phase='download'):
        if on_download:on_download(DownloadProgress(target.name,count,total,phase))
    check()
    target.parent.mkdir(parents=True, exist_ok=True)
    report(0,None,'verify')
    if target.is_file() and digest_file(target) == expected_hash:
        size=target.stat().st_size
        report(size,size,'cached')
        return
    temporary = None
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Xopilot-Voice-Installer/2.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            length=getattr(response,'headers',{}).get('Content-Length')
            total=int(length) if length and str(length).isdigit() and int(length)>0 else None
            count=0;report(count,total)
            with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".part", delete=False) as output:
                temporary = Path(output.name)
                while chunk := response.read(64 * 1024):
                    check()
                    output.write(chunk)
                    count+=len(chunk);report(count,total)
        check()
        if total is not None and count!=total:
            raise RuntimeError(f'Загрузка {target.name} оборвалась. Повторите установку.')
        report(count,total,'verify')
        if digest_file(temporary) != expected_hash:
            raise RuntimeError(f"Контрольная сумма {target.name} не совпала. Повторите установку.")
        check()
        os.replace(temporary, target)
        report(count,count,'ready')
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def install_voice_model(model, *, on_download=None, cancelled=None) -> None:
    base_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/{REVISION}/{model.directory}"
    for name, expected_hash in ((f"{model.name}.onnx", model.sha256),
                                (f"{model.name}.onnx.json", model.config_sha256)):
        download_verified(f"{base_url}/{name}", VOICE_DIR / name, expected_hash,
                          on_download=on_download,cancelled=cancelled)


def install_voice(voice_id: str, on_progress=None, *, on_download=None, cancelled=None) -> None:
    if voice_id not in VOICES:
        raise ValueError(f"Неизвестный голос Live: {voice_id}")
    profile = VOICES[voice_id]
    keys = dict.fromkeys((profile.ru.model_key, profile.en.model_key))
    for key in keys:
        if on_progress is not None:
            on_progress(f"Установка {profile.name}: {MODELS[key].name}…")
        install_voice_model(MODELS[key],on_download=on_download,cancelled=cancelled)
    if voice_id == "miku":
        from .miku_installer import install_miku
        install_miku(on_progress,on_download=on_download,cancelled=cancelled)


def install_all_voices(on_progress=None) -> None:
    keys = dict.fromkeys(
        variant.model_key
        for profile in VOICES.values()
        for variant in (profile.ru, profile.en)
    )
    for key in keys:
        install_voice_model(MODELS[key])
    from .miku_installer import install_miku
    install_miku(on_progress)
