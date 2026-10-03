"""
Файл: App/services/voice_installer.py
Описание: Установка Piper-моделей и обученного тембра Miku для голосов Live.

Её используют и интерфейс настроек, и scripts/install_russian_voice.py.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
import urllib.request

from .voice_catalog import MODELS, REVISION, VOICES, VOICE_DIR


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_verified(url: str, target: Path, expected_hash: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and digest_file(target) == expected_hash:
        return
    temporary = None
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Xopilot-Voice-Installer/2.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".part", delete=False) as output:
                temporary = Path(output.name)
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        if digest_file(temporary) != expected_hash:
            raise RuntimeError(f"Контрольная сумма {target.name} не совпала. Повторите установку.")
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def install_voice_model(model) -> None:
    base_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/{REVISION}/{model.directory}"
    for name, expected_hash in ((f"{model.name}.onnx", model.sha256),
                                (f"{model.name}.onnx.json", model.config_sha256)):
        download_verified(f"{base_url}/{name}", VOICE_DIR / name, expected_hash)


def install_voice(voice_id: str, on_progress=None) -> None:
    if voice_id not in VOICES:
        raise ValueError(f"Неизвестный голос Live: {voice_id}")
    profile = VOICES[voice_id]
    keys = dict.fromkeys((profile.ru.model_key, profile.en.model_key))
    for key in keys:
        if on_progress is not None:
            on_progress(f"Установка {profile.name}: {MODELS[key].name}…")
        install_voice_model(MODELS[key])
    if voice_id == "miku":
        from .miku_installer import install_miku
        install_miku(on_progress)


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
