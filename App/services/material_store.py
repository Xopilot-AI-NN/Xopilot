"""Managed local copies of attachments, independent of their original location."""
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from .paths import app_data_dir


def store_material(name, *, path=None, data=None):
    name = Path(name.replace('\\', '/')).name
    if not name or name in {'.', '..'}:
        raise ValueError('У файла нет имени')
    root = app_data_dir() / 'materials'
    root.mkdir(parents=True, exist_ok=True)
    fd, staging = tempfile.mkstemp(dir=root, prefix='.incoming-')
    try:
        with os.fdopen(fd, 'wb') as target:
            if data is not None:
                target.write(data)
            elif path:
                with open(path, 'rb') as source:
                    shutil.copyfileobj(source, target)
            else:
                raise ValueError('Не удалось прочитать выбранный файл')
        with open(staging, 'rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        destination_dir = root / digest
        destination_dir.mkdir(exist_ok=True)
        destination = destination_dir / name
        os.replace(staging, destination)
        return str(destination)
    finally:
        if os.path.exists(staging):
            os.unlink(staging)
