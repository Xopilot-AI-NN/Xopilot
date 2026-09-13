"""
Файл: scripts/install_russian_voice.py
Разработчик: DenBroLiik
Описание: Явная установка голосов COVE, Miku и Maple (ru/en) с проверкой SHA-256.
    Историческое имя команды сохранено; приложение само модели не скачивает.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from App.services.voice_catalog import MODELS, REVISION, VOICES, VOICE_DIR


def digest_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_model(model):
    base_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/{REVISION}/{model.directory}"
    for target, expected_hash in ((model.path, model.sha256), (model.config_path, model.config_sha256)):
        if target.is_file() and digest_file(target) == expected_hash:
            print(f"Уже установлен: {target.name}", flush=True)
            continue
        print(f"Загружаю {target.name}…", flush=True)
        temporary = None
        try:
            request = urllib.request.Request(f"{base_url}/{target.name}", headers={"User-Agent": "Xopilot-Voice-Installer"})
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
    print(f"Готов: {model.name}", flush=True)


def install(voice="all"):
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    profiles = VOICES.values() if voice == "all" else [VOICES[voice]]
    keys = dict.fromkeys(variant.model_key for profile in profiles for variant in (profile.ru, profile.en))
    # Две независимые загрузки, общий Irina для женских профилей скачивается один раз.
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(install_model, (MODELS[key] for key in keys)))
    print(f"Голоса готовы: {VOICE_DIR}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Установить голоса Live для русского и английского.")
    parser.add_argument("--voice", choices=["all", *VOICES], default="all")
    install(parser.parse_args().voice)
