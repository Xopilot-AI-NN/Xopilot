"""
Файл: scripts/install_russian_voice.py
Разработчик: DenBroLiik
Описание: CLI-установка голосов COVE, Miku и Maple (ru/en) с проверкой SHA-256.
    Историческое имя команды сохранено. Та же логика доступна из настроек Xopilot.
"""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from App.services.voice_catalog import VOICES, VOICE_DIR
from App.services.voice_installer import install_all_voices, install_voice


def install(voice="all"):
    if voice == "all":
        install_all_voices()
    else:
        install_voice(voice)
    print(f"Голоса готовы: {VOICE_DIR}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Установить голоса Live для русского и английского.")
    parser.add_argument("--voice", choices=["all", *VOICES], default="all")
    install(parser.parse_args().voice)
