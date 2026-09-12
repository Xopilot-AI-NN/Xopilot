"""
Файл: App/services/live_audio.py
Разработчик: DenBroLiik
Описание: Выделение голосовой реплики WebRTC VAD с остановкой после паузы.
    Ожидание речи хранит только последние 300 мс; звук обрабатывается в памяти.
"""

import io
import sys
import threading
import wave
from array import array
from collections import deque
from concurrent.futures import CancelledError

from .microphone import MAX_RECORDING_SECONDS, sd

try:
    import webrtcvad

    _IMPORT_ERROR = None
except Exception as exc:
    webrtcvad = None
    _IMPORT_ERROR = exc


FRAME_MS = 30
SILENCE_SECONDS = 0.9


def check_live_audio():
    if sd is None:
        raise RuntimeError("Для Live нужны sounddevice и PortAudio.")
    if webrtcvad is None:
        raise RuntimeError("Для Live установите зависимости приложения (webrtcvad-wheels).") from _IMPORT_ERROR


class SpeechSegmenter:
    """Выделяет одну фразу из последовательности кадров PCM16 по 30 мс."""

    def __init__(self, sample_rate=16000, vad=None, silence_seconds=SILENCE_SECONDS):
        self.sample_rate = sample_rate
        self._vad = vad if vad is not None else webrtcvad.Vad(2)
        self._pre_roll = deque(maxlen=10)
        self._chunks = []
        self._silent_frames = 0
        self._silence_limit = max(1, round(silence_seconds * 1000 / FRAME_MS))
        self._frame_limit = int(MAX_RECORDING_SECONDS * 1000 / FRAME_MS)
        self.started = False
        self.finished = False

    def feed(self, frame):
        if self.finished:
            return
        if len(frame) != self.sample_rate * FRAME_MS // 1000 * 2:
            raise ValueError("Неверный размер аудиокадра.")
        voiced = self._vad.is_speech(frame, self.sample_rate)
        if not self.started:
            self._pre_roll.append((frame, voiced))
            if sum(active for _, active in self._pre_roll) >= 6:
                self.started = True
                self._chunks.extend(data for data, _ in self._pre_roll)
                self._pre_roll.clear()
            return
        self._chunks.append(frame)
        self._silent_frames = 0 if voiced else self._silent_frames + 1
        self.finished = (
            self._silent_frames >= self._silence_limit
            or len(self._chunks) >= self._frame_limit
        )

    def wav_bytes(self):
        if not self.started:
            raise RuntimeError("Речь не обнаружена.")
        pcm = b"".join(self._chunks)
        if sys.byteorder != "little":
            samples = array("h", pcm)
            samples.byteswap()
            pcm = samples.tobytes()
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(pcm)
        return output.getvalue()


def record_utterance(cancelled: threading.Event) -> bytes:
    """Блокирующее ожидание одной фразы. Отмена закрывает устройство за один цикл ожидания."""
    check_live_audio()
    if cancelled.is_set():
        raise CancelledError()
    sample_rate = None
    for rate in (16000, 48000, 32000, 8000):
        try:
            sd.check_input_settings(channels=1, dtype="int16", samplerate=rate)
            sample_rate = rate
            break
        except Exception:
            continue
    if sample_rate is None:
        raise RuntimeError("Не удалось настроить микрофон для Live. Проверьте устройство ввода.")

    segment = SpeechSegmenter(sample_rate)
    finished = threading.Event()
    errors = []

    def receive(data, _frames, _time, status):
        if status:
            errors.append(RuntimeError("Микрофон потерял часть звука. Перезапустите Live."))
            raise sd.CallbackAbort
        try:
            segment.feed(bytes(data))
        except Exception as exc:
            errors.append(exc)
            raise sd.CallbackAbort
        if segment.finished:
            raise sd.CallbackStop

    stream = None
    try:
        stream = sd.RawInputStream(
            samplerate=sample_rate,
            blocksize=sample_rate * FRAME_MS // 1000,
            channels=1,
            dtype="int16",
            callback=receive,
            finished_callback=finished.set,
        )
        stream.start()
        while not finished.wait(0.05):
            if cancelled.is_set():
                raise CancelledError()
        if cancelled.is_set():
            raise CancelledError()
        if errors:
            raise errors[0]
        return segment.wav_bytes()
    finally:
        if stream is not None:
            try:
                stream.abort()
            finally:
                stream.close()
