"""
Файл: App/services/paths.py
Разработчик: DenBroLiik
Описание: Доступные для записи каталоги пользователя и старый каталог моделей.
"""

import os
import platform
from pathlib import Path

LEGACY_MODELS_DIR = Path(__file__).resolve().parents[1] / "data" / "models"


def app_data_dir() -> Path:
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", str(Path.home()))
    else:
        base = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))
    return Path(base) / "Xopilot"


def models_dir() -> Path:
    override = os.environ.get("XOPILOT_MODELS_DIR")
    return Path(override).expanduser() if override else app_data_dir() / "models"
