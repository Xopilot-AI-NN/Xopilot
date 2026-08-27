"""
Файл: /App/services/db.py
Разработчик: DenBroLiik
Описание: Единая точка доступа к локальной БД (Rust-модуль advanced_xopilot, Services/).
    Путь к файлу БД и ключ шифрования подбираются автоматически внутри Rust-кода (OS keyring).
    Все вызовы обёрнуты try/except: если модуль ещё не собран через `maturin develop`
    в Services/, UI всё равно должен открываться — настройки просто не будут сохраняться.
"""

import os
import platform
from typing import Optional

try:
    import advanced_xopilot  # type: ignore  # Rust cdylib из Services/, собирается отдельно
    _IMPORT_ERROR: Optional[Exception] = None
except Exception as exc:  # noqa: BLE001 — на этапе разработки модуль может быть ещё не собран
    advanced_xopilot = None  # type: ignore
    _IMPORT_ERROR = exc


def _app_data_dir() -> str:
    """Каталог данных приложения: %APPDATA%\\Xopilot на Windows, ~/.local/share/Xopilot на Linux."""
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    path = os.path.join(base, "Xopilot")
    os.makedirs(path, exist_ok=True)
    return path


_db = None  # единственный экземпляр PyDatabase на процесс приложения


def get_db():
    """Возвращает открытое соединение с БД (лениво, один раз за время жизни приложения).

    Поднимает RuntimeError, если advanced_xopilot не собран — вызывающий код должен 'reшать,
    что делать дальше (используйте get_setting/set_setting ниже — они это гасят сами).
    """
    global _db
    if _db is None:
        if advanced_xopilot is None:
            raise RuntimeError(
                "advanced_xopilot не собран — выполните `maturin develop` в Services/"
            ) from _IMPORT_ERROR
        db_path = os.path.join(_app_data_dir(), "xopilot.db")
        _db = advanced_xopilot.PyDatabase(db_path)
    return _db


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Безопасное чтение настройки — при недоступной БД возвращает default, не роняя UI."""
    try:
        value = get_db().get_setting(key)
        return value if value is not None else default
    except Exception:
        return default


def set_setting(key: str, value: str) -> bool:
    """Безопасная запись настройки. False — если БД недоступна (напр., до сборки Rust-модуля)."""
    try:
        get_db().set_setting(key, value)
        return True
    except Exception:
        return False