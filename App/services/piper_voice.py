"""
Файл: App/services/piper_voice.py
Разработчик: DenBroLiik
Описание: Локальная озвучка Piper с выбранным тембром, языком и отменой
    синтеза и воспроизведения. Модель загружается с диска, аудио остаётся в памяти.
"""

import threading
from concurrent.futures import CancelledError
from dataclasses import replace

from .microphone import sd


class _CancellableSession:
    """Передаёт сигнал отмены в ONNX Runtime, в том числе до готовности первого аудио."""

    def __init__(self, session, cancelled, run_options_factory):
        self._session = session
        self._cancelled = cancelled
        self._run_options_factory = run_options_factory

    def __getattr__(self, name):
        return getattr(self._session, name)

    def run(self, output_names, input_feed, run_options=None):
        if self._cancelled.is_set():
            raise CancelledError()
        options = run_options if run_options is not None else self._run_options_factory()
        finished = threading.Event()

        def watch_cancel():
            while not finished.wait(0.03):
                if self._cancelled.is_set():
                    options.terminate = True

        watcher = threading.Thread(target=watch_cancel, daemon=True)
        watcher.start()
        try:
            result = self._session.run(output_names, input_feed, run_options=options)
            if self._cancelled.is_set():
                raise CancelledError()
            return result
        except Exception:
            if self._cancelled.is_set():
                raise CancelledError() from None
            raise
        finally:
            finished.set()
            watcher.join()


class PiperSpeechVoice:
    def __init__(self, variant):
        try:
            import onnxruntime
            from piper import PiperVoice, SynthesisConfig
        except Exception as exc:
            raise RuntimeError("Для озвучки установите зависимости приложения (piper-tts).") from exc
        if sd is None:
            raise RuntimeError("Для озвучки нужны sounddevice и PortAudio.")
        model = variant.model
        if not model.installed:
            raise RuntimeError("Установите голоса: scripts/install_russian_voice.py")
        self._voice = PiperVoice.load(model.path, config_path=model.config_path, use_cuda=False)
        if self._voice.config.espeak_voice != model.espeak_voice:
            raise RuntimeError(f"Конфигурация {model.name} содержит другой язык.")
        # noise_w_scale — вариативность длительности фонем: чем больше, тем живее/естественнее
        # ритмика; чем меньше — тем ровнее/спокойнее (как у en_US-ljspeech по умолчанию).
        # None — берётся дефолт из .onnx.json самой модели (так устроен сам Piper).
        self._synthesis_config = SynthesisConfig(
            length_scale=variant.length_scale,
            noise_scale=variant.noise_scale,
            noise_w_scale=variant.noise_w_scale,
            volume=0.85,
        )
        self._rate_scale = variant.rate_scale
        self._run_options_factory = onnxruntime.RunOptions
        self._lock = threading.Lock()

    def synthesize(self, text, cancelled):
        """Аудио по предложениям: одна загруженная модель на весь голосовой разговор."""
        while not self._lock.acquire(timeout=0.05):
            if cancelled.is_set():
                raise CancelledError()
        original = self._voice.session
        try:
            if cancelled.is_set():
                raise CancelledError()
            # `session` в Piper имеет тип InferenceSession, но мы временно подменяем его
            # на cancellable обёртку, чтобы прерывать нативный вызов из другого потока.
            # Для типизатора это безопасный обход: атрибут меняется через словарь instance.
            self._voice.__dict__["session"] = _CancellableSession(
                original, cancelled, self._run_options_factory
            )
            for chunk in self._voice.synthesize(text, syn_config=self._synthesis_config):
                if cancelled.is_set():
                    raise CancelledError()
                if self._rate_scale != 1.0:
                    # Варианты женского тембра: меняем высоту и компенсируем темп
                    # через length_scale. COVE сохраняет исходную высоту диктора.
                    chunk = replace(chunk, sample_rate=round(chunk.sample_rate * self._rate_scale))
                yield chunk
        finally:
            self._voice.__dict__["session"] = original
            self._lock.release()

    def speak(self, text, cancelled):
        stream = None
        chunks = self.synthesize(text, cancelled)
        try:
            for chunk in chunks:
                if stream is None:
                    stream = sd.RawOutputStream(
                        samplerate=chunk.sample_rate,
                        channels=chunk.sample_channels,
                        dtype="int16",
                        latency="low",
                    )
                    stream.start()
                pcm = chunk.audio_int16_bytes
                # Пишем не больше 40 мс за вызов, чтобы кнопка «Перебить» не ждала конца фразы.
                block_bytes = max(1, chunk.sample_rate * 40 // 1000) * chunk.sample_channels * 2
                for offset in range(0, len(pcm), block_bytes):
                    if cancelled.is_set():
                        raise CancelledError()
                    stream.write(pcm[offset:offset + block_bytes])
            if cancelled.is_set():
                raise CancelledError()
            if stream is not None:
                stream.stop()
        finally:
            try:
                chunks.close()
            finally:
                if stream is not None:
                    try:
                        stream.abort()
                    finally:
                        stream.close()