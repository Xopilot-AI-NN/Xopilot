"""Файл: /App/services/mobile_audio.py
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: Запись Android без блокировки канала отмены и системная речь.
"""
import base64
import io
import threading
import time
import wave
from concurrent.futures import CancelledError
from types import SimpleNamespace
from . import mobile_runtime as runtime


def _wav(pcm):
    if len(pcm) < 8000:
        raise RuntimeError('Запись слишком короткая. Произнесите фразу ещё раз.')
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(pcm)
    return output.getvalue()


def _cancellable(operation, arguments, cancelled, stop):
    if cancelled.is_set(): raise CancelledError()
    finished = threading.Event()
    def watch():
        while not finished.wait(.05):
            if cancelled.is_set():
                runtime.call(stop)
                return
    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    try:
        result = runtime.call(operation, arguments)
        if cancelled.is_set(): raise CancelledError()
        return result
    except Exception:
        if cancelled.is_set(): raise CancelledError() from None
        raise
    finally:
        finished.set(); watcher.join()


class AndroidRecorder:
    def __init__(self, max_seconds=30):
        self.max_seconds = min(30, max_seconds)
        self._started = None

    @property
    def elapsed(self): return min(self.max_seconds, time.monotonic()-self._started) if self._started is not None else 0

    @property
    def finished(self): return self._started is not None and self.elapsed >= self.max_seconds

    def start(self):
        runtime.call('audioStart')
        self._started = time.monotonic()

    def stop(self):
        try: return _wav(base64.b64decode(runtime.call('audioStop'), validate=True))
        finally: self._started = None

    def cancel(self):
        try: runtime.call('audioCancel')
        finally: self._started = None


def record_utterance(cancelled, *, on_speech_start=None, echo_cancellation=False):
    if cancelled.is_set():
        raise CancelledError()
    print('XopilotAudio: begin recording', flush=True)
    runtime.call('audioBeginUtterance', {'echoCancellation': True}) if echo_cancellation else runtime.call('audioBeginUtterance')
    print('XopilotAudio: recorder ready', flush=True)
    notified = False
    next_diagnostic = time.monotonic() + 5
    try:
        # Each bridge request returns promptly even while waiting for speech.
        # A long recordUtterance invocation can otherwise hold up audioCancel.
        while not cancelled.is_set():
            result = runtime.call('audioPollUtterance')
            if result.get('speechStarted') and not notified:
                notified = True
                if on_speech_start and not cancelled.is_set():
                    on_speech_start()
            if time.monotonic() >= next_diagnostic:
                print(f"XopilotAudio: received bytes={result.get('bytes', 0)}, peak={result.get('peak', 0):.0f}", flush=True)
                if result.get('bytes') == 0:
                    raise RuntimeError('Микрофон открыт, но звук не поступает. Проверьте доступ к микрофону и повторите разговор.')
                next_diagnostic = time.monotonic() + 5
            if result['state'] == 'done':
                return _wav(base64.b64decode(result['data'], validate=True))
            if result['state'] == 'error':
                raise RuntimeError(result['error'])
            cancelled.wait(.08)
        raise CancelledError()
    finally:
        print('XopilotAudio: cancelling recorder', flush=True)
        runtime.call('audioCancel')
        print('XopilotAudio: recorder released', flush=True)


class AndroidSpeechOutput:
    def __init__(self):
        self.profile = SimpleNamespace(id='android-system', name='Системный офлайн-голос Android')
        self.backend = 'android-tts-offline'

    def speak(self, text, cancelled):
        from .speech_output import spoken_text, speech_segments
        for language, part in speech_segments(spoken_text(text)):
            _cancellable('speak', {'language': language, 'text': part}, cancelled, 'stopSpeech')


def record_barge_in(cancelled, on_speech_start):
    """Listen during playback only when the native recorder enables AEC."""
    return record_utterance(cancelled, on_speech_start=on_speech_start, echo_cancellation=True)
