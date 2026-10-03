"""Keep runtime writes outside the source tree watched by `flet run -r`."""
import os
import tempfile
from .paths import app_data_dir


def cache_dir():
    path = app_data_dir() / "cache" / "litert"
    path.mkdir(parents=True, exist_ok=True)
    return path


def configure_runtime():
    root = app_data_dir().resolve()
    for key, name in (("FLET_APP_STORAGE_DATA", "runtime"),
                      ("FLET_APP_STORAGE_CACHE", "cache"),
                      ("FLET_APP_STORAGE_TEMP", "tmp")):
        path = root / name
        path.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(path)
    for key in ("TMPDIR", "TEMP", "TMP"):
        os.environ[key] = os.environ["FLET_APP_STORAGE_TEMP"]
    tempfile.tempdir = None
    # The Flet CLI starts the child in App/.flet/storage/data. Native libraries
    # also write relative caches there, independently of Python's temp directory.
    os.chdir(os.environ["FLET_APP_STORAGE_DATA"])
