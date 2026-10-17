"""
Файл: /App/services/miku_installer.py
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: Установка Miku и автоматическая подготовка изолированной среды экспорта.
"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import venv
import time
import re
from concurrent.futures import CancelledError

from .miku_models import RESOURCES, model_directory, miku_installed
from .paths import app_data_dir


_INSTALL_LOCK = threading.Lock()


def _command(args, log_path, cwd, timeout=1200, cancelled=None, on_download=None):
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    # Embedded/Flet Python paths must not override the isolated export interpreter.
    for name in ("PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE", "VIRTUAL_ENV"):
        environment.pop(name, None)
    with log_path.open("a", encoding="utf-8") as log:
        offset=log.tell()
        process = subprocess.Popen(args,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,env=environment)
        deadline=time.monotonic()+timeout
        try:
            with log_path.open(encoding='utf-8',errors='replace') as updates:
                updates.seek(offset)
                while process.poll() is None:
                    if cancelled is not None and cancelled.is_set():raise CancelledError()
                    if time.monotonic()>=deadline:raise TimeoutError('Подготовка Miku заняла слишком много времени. Повторите установку.')
                    for line in updates.readlines():
                        match=re.fullmatch(r'Progress (\d+) of (\d+)\s*',line)
                        if match and on_download:
                            from .voice_installer import DownloadProgress
                            downloaded,total=map(int,match.groups())
                            on_download(DownloadProgress('Компоненты подготовки Miku',downloaded,total or None))
                    time.sleep(.1)
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:process.kill();process.wait()
    if process.returncode:
        raise RuntimeError(f"Подготовка Miku не завершена. Повторите установку после проверки сети и свободного места. Журнал: {log_path}")


def _export_python(on_progress, *, on_download=None, cancelled=None):
    # Optional existing environment for developers/build machines; never used in inference.
    supplied = os.environ.get("XOPILOT_RVC_EXPORT_PYTHON")
    if supplied:
        # Resolving symlinks would turn a venv's bin/python into the base Python,
        # losing that environment's export dependencies on Linux.
        candidate = Path(os.path.abspath(Path(supplied).expanduser()))
        if not candidate.is_file():
            raise RuntimeError("XOPILOT_RVC_EXPORT_PYTHON не указывает на Python.")
        return candidate
    runtime = app_data_dir() / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    environment = runtime / "miku-export"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    marker = environment / "xopilot-export-ready-v1"
    if marker.is_file() and python.is_file():
        return python
    # A packaged launcher is not Python. Bootstrap a pinned interpreter instead
    # of executing Xopilot recursively or requiring terminal commands.
    embedded=not Path(sys.executable).name.lower().startswith('python') or bool(getattr(sys,'frozen',False))
    runtime_python=None
    if embedded:
        from .voice_runtime import export_runtime
        runtime_python=export_runtime(on_progress,on_download=on_download,cancelled=cancelled)
    on_progress("Miku: готовлю отдельную среду экспорта. Это требуется только при первой установке…")
    try:
        if runtime_python:
            _command([str(runtime_python),'-m','venv',str(environment)],runtime/'miku-install.log',runtime,
                     cancelled=cancelled)
        else:venv.EnvBuilder(with_pip=True, symlinks=os.name != "nt").create(environment)
    except CancelledError:raise
    except Exception as exc:
        raise RuntimeError(
            "Не удалось подготовить среду Miku. Проверьте свободное место и повторите установку."
        ) from exc
    log = runtime / "miku-install.log"
    # CPU wheels avoid installing an entire CUDA stack for a one-time conversion.
    on_progress('Устанавливаю компоненты подготовки Miku. Это может занять несколько минут…')
    # pip >=25.2 can resume interrupted wheel downloads. The bundled pip first
    # updates itself using options available in its older version too.
    _command([str(python),'-m','pip','install','--progress-bar','raw','--only-binary=:all:',
              '--timeout','60','--retries','5','pip>=25.2,<27','--index-url','https://pypi.org/simple'],
             log,runtime,cancelled=cancelled,on_download=on_download,timeout=3600)
    network=['--timeout','60','--retries','5','--resume-retries','5']
    _command([str(python), "-m", "pip", "install", '--progress-bar','raw','--only-binary=:all:',*network, "torch>=2.10,<3",
              "--index-url", "https://download.pytorch.org/whl/cpu"], log, runtime,cancelled=cancelled,on_download=on_download,timeout=3600)
    _command([str(python), "-m", "pip", "install", "numpy>=1.26,<3", "scipy>=1.15,<2",
              "onnx>=1.17,<2", "onnxruntime>=1.20,<2",
              '--progress-bar','raw','--only-binary=:all:',*network, "--index-url", "https://pypi.org/simple"], log, runtime,cancelled=cancelled,on_download=on_download,timeout=3600)
    marker.write_text("1", encoding="utf-8")
    return python


def install_miku(on_progress=None, *, on_download=None, cancelled=None):
    from .voice_installer import download_verified, digest_file
    on_progress = on_progress or (lambda _: None)
    with _INSTALL_LOCK:
        root = model_directory()
        root.mkdir(parents=True, exist_ok=True)
        for name, (url, sha256) in RESOURCES.items():
            on_progress(f"Miku: проверяю и загружаю {name}…")
            download_verified(url, root / name, sha256,on_download=on_download,cancelled=cancelled)
        if miku_installed():
            import json
            metadata = json.loads((root / "miku.json").read_text(encoding="utf-8"))
            if digest_file(root / "miku.onnx") == metadata["onnx_sha256"]:
                return root
        python = _export_python(on_progress,on_download=on_download,cancelled=cancelled)
        on_progress("Miku: конвертирую модель и проверяю совпадение звука с оригиналом…")
        # Never promote an incomplete or unvalidated ONNX model.
        with tempfile.TemporaryDirectory(dir=root, prefix="export-") as temporary:
            stage = Path(temporary)
            from .voice_runtime import stage_export_sources
            package_parent = stage_export_sources(stage/'sources')
            log = root / "export.log"
            args = [str(python), "-m", "_rvc_export.export",
                    str(root / "miku.pth"), str(stage / "miku.onnx")]
            _command(args, log, package_parent,cancelled=cancelled)
            if cancelled is not None and cancelled.is_set():raise CancelledError()
            os.replace(stage / "miku.onnx", root / "miku.onnx")
            os.replace(stage / "miku.json", root / "miku.json")
        if not miku_installed():
            raise RuntimeError("Miku не прошла проверку после установки.")
        on_progress("Miku установлена. Для озвучки интернет и PyTorch больше не нужны.")
        return root
