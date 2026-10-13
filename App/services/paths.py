"""
Файл: App/services/paths.py
Разработчик: DenBroLiik
Описание: Доступные для записи каталоги пользователя и старый каталог моделей.
"""

import os
import platform
from pathlib import Path
from .platforms import is_android

# Preserve the app-private root supplied by Flet before configure_runtime moves
# its working/temp directories. Re-reading the rewritten variable would nest
# a new Xopilot/runtime directory on every call.
_ANDROID_DATA_ROOT = os.environ.get("FLET_APP_STORAGE_DATA")

LEGACY_MODELS_DIR = Path(__file__).resolve().parents[1] / "data" / "models"


def app_data_dir() -> Path:
    if is_android():
        if not _ANDROID_DATA_ROOT:
            raise RuntimeError("Android не предоставил закрытый каталог данных приложения.")
        return Path(_ANDROID_DATA_ROOT) / "Xopilot"
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", str(Path.home()))
    else:
        base = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))
    return Path(base) / "Xopilot"


def models_dir() -> Path:
    override = os.environ.get("XOPILOT_MODELS_DIR")
    return Path(override).expanduser() if override else app_data_dir() / "models"
