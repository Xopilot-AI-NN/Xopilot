"""Keep runtime writes outside the source tree watched by `flet run -r`."""
import os
import tempfile
import time
from .paths import app_data_dir
from .platforms import is_android


def configure_android_tls():
    # Embedded OpenSSL cannot read Android's Java certificate store. Supply the
    # packaged CA bundle to urllib too, keeping certificate checks enabled.
    if is_android() and 'SSL_CERT_FILE' not in os.environ:
        import certifi
        os.environ['SSL_CERT_FILE'] = certifi.where()


def release_unused_memory():
    """Return freed native allocations to glibc without discarding live mappings."""
    import gc
    import sys
    gc.collect()
    if sys.platform.startswith("linux"):
        import ctypes
        try:
            trim = ctypes.CDLL(None).malloc_trim
            trim.argtypes = [ctypes.c_size_t]
            trim.restype = ctypes.c_int
            trim(0)
        except (AttributeError, OSError):
            pass


class IdleMemoryCleanup:
    """Release disposable caches after quiet periods, never during a request."""
    def __init__(self, interval=60):
        self.interval = interval
        self.activity()

    def activity(self):
        self._last_activity = time.monotonic()

    async def poll(self, page, *, model_released=False):
        import asyncio
        eligible = getattr(page, '_xopilot_can_release_memory',
                           getattr(page, '_xopilot_can_release_model', lambda: False))
        busy = not eligible()
        dialogs = getattr(page, '_dialogs', None)
        if busy or any(dialog.open for dialog in (dialogs.controls if dialogs is not None else ())):
            self.activity()
            return False
        if not model_released and time.monotonic() - self._last_activity < self.interval:
            return False
        self.activity()
        # Cached thumbnails can be recreated from originals; saved content and
        # current controls are not discarded. Keep the media module lazy.
        import sys
        for name in ('App.app.materials.material', 'app.materials.material'):
            module = sys.modules.get(name)
            if module is not None:
                module._image_preview.cache_clear()
        await asyncio.to_thread(release_unused_memory)
        if is_android():
            from .mobile_runtime import call_async
            await call_async('releaseMemory')
        return True


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
    configure_android_tls()
    # The Flet CLI starts the child in App/.flet/storage/data. Native libraries
    # also write relative caches there, independently of Python's temp directory.
    os.chdir(os.environ["FLET_APP_STORAGE_DATA"])
