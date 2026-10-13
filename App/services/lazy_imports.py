"""Load optional media libraries only when their feature is used."""
import importlib
import threading


class OptionalModule:
    def __init__(self, name):
        self.name = name
        self._module = None
        self._attempted = False
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if not self._attempted:
                try:
                    self._module = importlib.import_module(self.name)
                except Exception:
                    self._module = None
                self._attempted = True
            return self._module

    def __bool__(self):
        return self._load() is not None

    def __getattr__(self, name):
        module = self._load()
        if module is None:
            raise ImportError(f"Не удалось загрузить {self.name}")
        return getattr(module, name)
