"""
Файл: App/services/live_vision.py
Описание: Захват одного кадра с камеры или экрана для Live-разговора — чтобы
    мультимодальная модель «видела», что происходит в момент реплики. Синхронные блокирующие
    вызовы — вызывающая сторона (App/app/live_conversation.py) должна заворачивать через asyncio.to_thread.
"""

import io

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


def capture_camera_frame(device_index: int = 0) -> bytes:
    """Один кадр с веб-камеры как JPEG-байты. Бросает RuntimeError, если камера недоступна."""
    if cv2 is None:
        raise RuntimeError("Для камеры в Live нужен opencv-python — не установлен.")
    cap = cv2.VideoCapture(device_index)
    try:
        if not cap.isOpened():
            raise RuntimeError("Не удалось открыть камеру.")
        # Первый кадр после открытия часто чёрный/недоэкспонирован — даём сенсору пару кадров на разгон.
        frame = None
        for _ in range(5):
            ok, frame = cap.read()
            if not ok:
                frame = None
                break
        if frame is None:
            raise RuntimeError("Не удалось получить кадр с камеры.")
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            raise RuntimeError("Не удалось закодировать кадр камеры.")
        return buf.tobytes()
    finally:
        cap.release()


def capture_screen_frame(monitor_index: int = 0) -> bytes:
    """Снимок экрана (монитор monitor_index, 0 = все мониторы целиком в mss) как JPEG-байты,
    уменьшенный до MAX_SIDE по длинной стороне. Бросает RuntimeError, если недоступно.
    """
    if mss is None:
        raise RuntimeError("Для трансляции экрана в Live нужен mss — не установлен.")
    if Image is None:
        raise RuntimeError("Для трансляции экрана в Live нужен Pillow — не установлен.")
    with mss.mss() as sct:
        monitors = sct.monitors
        index = monitor_index if 0 <= monitor_index < len(monitors) else 0
        shot = sct.grab(monitors[index])
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        return out.getvalue()