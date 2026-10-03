"""Install pinned Miku resources; export once in an isolated CPU-only environment."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import venv

from .miku_models import RESOURCES, model_directory, miku_installed
from .paths import app_data_dir


_INSTALL_LOCK = threading.Lock()


def _command(args, log_path, cwd, timeout=1200):
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    # Embedded/Flet Python paths must not override the isolated export interpreter.
    for name in ("PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE", "VIRTUAL_ENV"):
        environment.pop(name, None)
    with log_path.open("a", encoding="utf-8") as log:
        result = subprocess.run(args, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                env=environment,
                                timeout=timeout, check=False)
    if result.returncode:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-1400:]
        raise RuntimeError(f"Подготовка Miku не завершена. Журнал: {log_path}\n{tail}")


def _export_python(on_progress):
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
    # A packaged Flet app is an embedded interpreter. Asking venv to execute
    # Xopilot as though it were Python can open another application window.
    if not Path(sys.executable).name.lower().startswith("python"):
        raise RuntimeError(
            "Для первого экспорта Miku запустите scripts/install_russian_voice.py --voice miku "
            "через Python 3.14 с pip. После подготовки голос доступен и в установленном приложении."
        )
    on_progress("Miku: готовлю отдельную среду экспорта. Это требуется только при первой установке…")
    try:
        venv.EnvBuilder(with_pip=True, symlinks=os.name != "nt").create(environment)
    except Exception as exc:
        raise RuntimeError(
            "Не удалось создать среду экспорта Miku. Запустите scripts/install_russian_voice.py "
            "--voice miku через обычный Python с pip. Модели сохранятся в профиле Xopilot."
        ) from exc
    log = runtime / "miku-install.log"
    # CPU wheels avoid installing an entire CUDA stack for a one-time conversion.
    _command([str(python), "-m", "pip", "install", "torch>=2.10,<3",
              "--index-url", "https://download.pytorch.org/whl/cpu"], log, runtime)
    _command([str(python), "-m", "pip", "install", "numpy>=1.26,<3", "scipy>=1.15,<2",
              "onnx>=1.17,<2", "onnxruntime>=1.20,<2",
              "--index-url", "https://pypi.org/simple"], log, runtime)
    marker.write_text("1", encoding="utf-8")
    return python


def install_miku(on_progress=None):
    from .voice_installer import download_verified, digest_file
    on_progress = on_progress or (lambda _: None)
    with _INSTALL_LOCK:
        root = model_directory()
        root.mkdir(parents=True, exist_ok=True)
        for name, (url, sha256) in RESOURCES.items():
            on_progress(f"Miku: проверяю и загружаю {name}…")
            download_verified(url, root / name, sha256)
        if miku_installed():
            import json
            metadata = json.loads((root / "miku.json").read_text(encoding="utf-8"))
            if digest_file(root / "miku.onnx") == metadata["onnx_sha256"]:
                return root
        python = _export_python(on_progress)
        on_progress("Miku: конвертирую модель и проверяю совпадение звука с оригиналом…")
        # Never promote an incomplete or unvalidated ONNX model.
        with tempfile.TemporaryDirectory(dir=root, prefix="export-") as temporary:
            stage = Path(temporary)
            package_parent = Path(__file__).resolve().parents[1]
            log = root / "export.log"
            args = [str(python), "-m", "services._rvc_export.export",
                    str(root / "miku.pth"), str(stage / "miku.onnx")]
            _command(args, log, package_parent)
            os.replace(stage / "miku.onnx", root / "miku.onnx")
            os.replace(stage / "miku.json", root / "miku.json")
        if not miku_installed():
            raise RuntimeError("Miku не прошла проверку после установки.")
        on_progress("Miku установлена. Для озвучки интернет и PyTorch больше не нужны.")
        return root
