"""Explicit local exports, also usable when an embedded browser blocks downloads."""
from pathlib import Path
import shutil
import uuid
from .paths import app_data_dir


def save_local_export(name, data):
    name = Path(name.replace('\\', '/')).name
    if name in {'', '.', '..'}:
        raise ValueError('Укажите имя файла')
    root = app_data_dir() / 'exports'
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder = root / uuid.uuid4().hex
    folder.mkdir(mode=0o700)
    path = folder / name
    try:
        with path.open('xb') as output:
            path.chmod(0o600)
            output.write(data)
        return str(path)
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
