"""Persist the inference preference and inspect free discrete GPU memory."""
import os
import platform
import subprocess
import time
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
    from .platforms import is_android
    if is_android():
        # Mobile GPUs share system memory; desktop NVIDIA/DRI probes do not
        # describe them. Ask the Android runtime/driver and keep Auto fallback.
        return (["gpu", "cpu"] if mode == "auto" else ["gpu"]), ""
    devices = nvidia_devices()
    if mode == "auto" and devices:
        # The container also includes CPU embedders, encoders and tokenizer data:
        # its total size is not the GPU allocation size. Let the driver validate
        # capacity, instead of rejecting a model which could fit on the GPU.
        if not any(free > 0 for _, free, _ in devices):
            return ["cpu"], "Нет свободной видеопамяти; используется CPU"
        if not any(free > 0 and busy < 80 for _, free, busy in devices):
            # One utilization sample can capture a desktop redraw or a previous
            # model's final kernels. Avoid taking a GPU with sustained heavy work.
            # NVIDIA's utilization window can span one second; 250 ms still
            # sees the unloaded engine's work and incorrectly selects CPU.
            time.sleep(1.1)
            second = nvidia_devices() or devices
            if not any(free > 0 and busy < 80 for _, free, busy in second):
                return ["cpu"], "Видеокарта загружена; используется CPU"
    if devices and platform.system() == "Linux":
        # On hybrid laptops keep the integrated display GPU available for the UI.
        icd = Path("/usr/share/vulkan/icd.d/nvidia_icd.json")
        if icd.is_file():
            os.environ.setdefault("VK_DRIVER_FILES", str(icd))
    if mode == "auto" and platform.system() == "Linux" and not devices and not list(Path("/dev/dri").glob("renderD*")):
        return ["cpu"], "Совместимая видеокарта не обнаружена"
    return (["gpu", "cpu"] if mode == "auto" else ["gpu"]), ""
