"""Persist the inference preference and inspect free discrete GPU memory."""
import os
import platform
import subprocess
from pathlib import Path
from .db import get_setting, set_setting

MODES = {"auto": "Автоматически · свободная GPU", "gpu": "GPU · видеокарта", "cpu": "CPU · процессор"}


def preference():
    value = get_setting("inference_backend", "auto")
    return value if value in MODES else "auto"


def set_preference(value):
    if value not in MODES:
        raise ValueError("Неизвестный режим ускорения")
    if not set_setting("inference_backend", value):
        raise RuntimeError("Не удалось сохранить устройство вычислений")
    return True


def nvidia_devices():
    try:
        output = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.free,utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3, check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
        ).stdout
        return [(name.strip(), int(free.strip()) * 1024**2, int(busy.strip()))
                for name, free, busy in (line.rsplit(",", 2) for line in output.splitlines() if line.strip())]
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def candidates(model_path, mode):
    if mode == "cpu":
        return ["cpu"], "Выбран процессор"
    devices = nvidia_devices()
    if mode == "auto" and devices:
        # Weight size plus space for KV cache, kernels and working buffers. Driver
        # allocation remains the final check; failed GPU initialization falls back.
        required = Path(model_path).stat().st_size + 1024**3
        if not any(free >= required and busy < 20 for _, free, busy in devices):
            return ["cpu"], "Видеокарта занята или недостаточно свободной видеопамяти"
    if devices and platform.system() == "Linux":
        # On hybrid laptops keep the integrated display GPU available for the UI.
        icd = Path("/usr/share/vulkan/icd.d/nvidia_icd.json")
        if icd.is_file():
            os.environ.setdefault("VK_DRIVER_FILES", str(icd))
    if mode == "auto" and platform.system() == "Linux" and not devices and not list(Path("/dev/dri").glob("renderD*")):
        return ["cpu"], "Совместимая видеокарта не обнаружена"
    return (["gpu", "cpu"] if mode == "auto" else ["gpu"]), ""
