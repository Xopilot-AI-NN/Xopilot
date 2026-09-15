"""
Файл: App/services/microphone.py
Разработчик: DenBroLiik
Описание: Ограниченная по времени запись микрофона в памяти, моно PCM WAV.
    Блокирующие методы вызываются через asyncio.to_thread, без зависимостей от UI.
"""

import io
import sys
import threading
import time
import wave
from array import array

try:
    import sounddevice as sd

    _IMPORT_ERROR = None
except Exception as exc:
    sd = None
    _IMPORT_ERROR = exc


# Один аудиосегмент Gemma 4 поддерживает до 30 секунд.
MAX_RECORDING_SECONDS = 30


class MicrophoneRecorder:
    def __init__(self, max_seconds=MAX_RECORDING_SECONDS):
        self.max_seconds = max_seconds
        self._lock = threading.Lock()
        self._stream = None
        self._chunks = []
        self._frames = 0
        self._sample_rate = 16000
        self._started_at = None
        self._finished = threading.Event()
        self._error = None

    @property
    def elapsed(self):
        if self._started_at is None:
            return 0.0
        return min(time.monotonic() - self._started_at, self.max_seconds)

    @property
    def finished(self):
        return self._finished.is_set() or self.elapsed >= self.max_seconds

    def start(self):
        with self._lock:
            if self._stream is not None:
                raise RuntimeError("Микрофон уже записывает звук.")
            if sd is None:
                raise RuntimeError(
                    "Микрофон недоступен: нужны sounddevice и PortAudio. "
                    "Установите зависимости приложения; в Linux также нужен PortAudio."
                ) from _IMPORT_ERROR
            self._chunks.clear()
            self._frames = 0
            self._error = None
            self._finished.clear()
            try:
                device = sd.query_devices(kind="input")
                if device["max_input_channels"] < 1:
                    raise RuntimeError("Не найден микрофон.")
                # Используем частоту устройства: не все драйверы принимают 16 кГц.
                self._sample_rate = int(device["default_samplerate"])
                self._stream = sd.RawInputStream(
                    samplerate=self._sample_rate,
                    channels=1,
                    dtype="int16",
                    callback=self._receive,
                    finished_callback=self._finished.set,
                )
                self._started_at = time.monotonic()
                self._stream.start()
            except Exception as exc:
                self._close_stream()
                self._chunks.clear()
                self._started_at = None
                raise RuntimeError(
                    "Не удалось включить микрофон. Проверьте устройство ввода "
                    "и разрешение на запись звука в настройках системы."
                ) from exc

    def _receive(self, data, frames, _time, status):
        if status:
            self._error = "Запись звука прервалась. Проверьте микрофон и повторите диктовку."
            assert sd is not None
            raise sd.CallbackAbort
        remaining = int(self.max_seconds * self._sample_rate) - self._frames
        count = min(frames, remaining)
        self._chunks.append(bytes(data)[:count * 2])
        self._frames += count
        if count == remaining:
            assert sd is not None
            raise sd.CallbackStop

    def _close_stream(self):
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.abort()
            finally:
                stream.close()
        self._finished.set()

    def stop(self):
        """Освободить устройство и вернуть WAV; исходная запись больше не хранится."""
        with self._lock:
            try:
                self._close_stream()
                if self._error:
                    raise RuntimeError(self._error)
                if self._frames < self._sample_rate * 0.25:
                    raise RuntimeError("Запись слишком короткая. Нажмите микрофон и произнесите фразу.")
                samples = array("h", b"".join(self._chunks))
                if not samples or max(abs(sample) for sample in samples) < 32:
                    raise RuntimeError("Звук не слышен. Проверьте, что микрофон включён, и повторите.")
                if sys.byteorder != "little":
                    samples.byteswap()
                output = io.BytesIO()
                with wave.open(output, "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(self._sample_rate)
                    wav.writeframes(samples.tobytes())
                return output.getvalue()
            finally:
                self._chunks.clear()
                self._frames = 0
                self._started_at = None

    def cancel(self):
        with self._lock:
            try:
                self._close_stream()
            finally:
                self._chunks.clear()
                self._frames = 0
                self._started_at = None
