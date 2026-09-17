"""
Файл: App/services/voice_installer.py
Описание: Общая логика установки Piper-моделей голосов Live.

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


def install_voice_model(model) -> None:
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    base_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/{REVISION}/{model.directory}"
    for target, expected_hash in (
        (model.path, model.sha256),
        (model.config_path, model.config_sha256),
    ):
        if target.is_file() and digest_file(target) == expected_hash:
            continue

        temporary = None
        try:
            request = urllib.request.Request(
                f"{base_url}/{target.name}",
                headers={"User-Agent": "Xopilot-Voice-Installer/2.0"},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                with tempfile.NamedTemporaryFile(dir=VOICE_DIR, suffix=".part", delete=False) as output:
                    temporary = Path(output.name)
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
            if digest_file(temporary) != expected_hash:
                raise RuntimeError(f"Контрольная сумма {target.name} не совпала. Повторите установку.")
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def install_voice(voice_id: str) -> None:
    if voice_id not in VOICES:
        raise ValueError(f"Неизвестный голос Live: {voice_id}")
    profile = VOICES[voice_id]
    keys = dict.fromkeys((profile.ru.model_key, profile.en.model_key))
    for key in keys:
        install_voice_model(MODELS[key])


def install_all_voices() -> None:
    keys = dict.fromkeys(
        variant.model_key
        for profile in VOICES.values()
        for variant in (profile.ru, profile.en)
    )
    for key in keys:
        install_voice_model(MODELS[key])
