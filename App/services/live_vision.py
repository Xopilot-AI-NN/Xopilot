"""
Файл: App/services/live_vision.py
Описание: Захват одного кадра с камеры или экрана для Live-разговора — чтобы
    мультимодальная модель «видела», что происходит в момент реплики. Синхронные блокирующие
    вызовы — вызывающая сторона (App/app/live_conversation.py) должна заворачивать через asyncio.to_thread.

    Экран: под Wayland mss (через XWayland) возвращает ЧЁРНЫЙ кадр без всякой ошибки, поэтому
    в Wayland-сессии сначала пробуем CLI композитора (spectacle / grim / gnome-screenshot), а любой
    полностью чёрный кадр считаем ошибкой, а не отправляем модели.
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import time

try:
    import cv2
except Exception:
    cv2 = None
try:
    import mss
except Exception:
    mss = None
try:
    from PIL import Image
except Exception:
    Image = None

MAX_SIDE = 1024
# Автоэкспозиция веб-камеры сходится за десятые доли секунды: первые кадры серые/тёмные.
CAMERA_WARMUP_SECONDS = 0.8
CAMERA_MIN_FRAMES = 5
CAMERA_MAX_READS = 60
# Максимальная яркость пикселя, ниже которой кадр считается пустым (чёрным).
BLANK_MAX_LEVEL = 8


def capture_camera_frame(device_index: int = 0) -> bytes:
    """Один кадр с веб-камеры как JPEG-байты. Бросает RuntimeError, если камера недоступна."""
    if cv2 is None:
        raise RuntimeError("Для камеры в Live нужен opencv-python — не установлен.")
    backend = cv2.CAP_V4L2 if sys.platform.startswith("linux") else cv2.CAP_ANY
    cap = cv2.VideoCapture(device_index, backend)
    try:
        if not cap.isOpened():
            raise RuntimeError("Не удалось открыть камеру (занята другим приложением или нет доступа к устройству).")
        frame = None
        good = 0
        started = time.monotonic()
        for _ in range(CAMERA_MAX_READS):
            ok, current = cap.read()
            if ok:
                frame = current
                good += 1
            if good >= CAMERA_MIN_FRAMES and time.monotonic() - started >= CAMERA_WARMUP_SECONDS:
                break
        if frame is None:
            raise RuntimeError("Не удалось получить кадр с камеры.")
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            raise RuntimeError("Не удалось закодировать кадр камеры.")
        return buf.tobytes()
    finally:
        cap.release()


def _is_wayland() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY")) or os.environ.get("XDG_SESSION_TYPE") == "wayland"


def _is_blank(image) -> bool:
    return image.convert("L").getextrema()[1] <= BLANK_MAX_LEVEL


def _grab_mss(monitor_index: int):
    if mss is None:
        raise RuntimeError("не установлен mss")
    with mss.mss() as sct:
        monitors = sct.monitors
        index = monitor_index if 0 <= monitor_index < len(monitors) else 0
        shot = sct.grab(monitors[index])
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def _grab_cli(_monitor_index: int):
    """Снимок всего экрана через CLI композитора (работает под Wayland). Монитор не выбирается."""
    tools = (
        ("spectacle", lambda path: ["spectacle", "-b", "-n", "-f", "-o", path]),
        ("grim", lambda path: ["grim", path]),
        ("gnome-screenshot", lambda path: ["gnome-screenshot", "-f", path]),
    )
    available = [(name, build) for name, build in tools if shutil.which(name)]
    if not available:
        raise RuntimeError("нет spectacle / grim / gnome-screenshot")
    errors = []
    with tempfile.TemporaryDirectory(prefix="xopilot-shot-") as directory:
        path = os.path.join(directory, "screen.png")
        for name, build in available:
            try:
                subprocess.run(build(path), check=True, timeout=15,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                with Image.open(path) as shot:
                    return shot.convert("RGB")
            except Exception as exc:
                errors.append(f"{name}: {exc}")
    raise RuntimeError("; ".join(errors))


def capture_screen_frame(monitor_index: int = 0) -> bytes:
    """Снимок экрана как JPEG-байты, уменьшенный до MAX_SIDE по длинной стороне.
    Бросает RuntimeError с причиной, если снять экран не удалось или кадр получился чёрным.
    """
    if Image is None:
        raise RuntimeError("Для трансляции экрана в Live нужен Pillow — не установлен.")
    grabbers = [("mss", _grab_mss), ("снимок композитора", _grab_cli)]
    if _is_wayland():
        grabbers.reverse()
    reasons = []
    for name, grab in grabbers:
        try:
            image = grab(monitor_index)
        except Exception as exc:
            reasons.append(f"{name}: {exc}")
            continue
        if _is_blank(image):
            reasons.append(f"{name}: чёрный кадр")
            continue
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        out = io.BytesIO()
        image.convert("RGB").save(out, format="JPEG", quality=85)
        return out.getvalue()
    raise RuntimeError("Не удалось снять экран (" + "; ".join(reasons) + ").")