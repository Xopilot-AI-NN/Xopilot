"""Local learned Miku timbre: Piper pronunciation → ContentVec/RMVPE → RVC.

DSP follows RVC-Project's RMVPE preprocessing (MIT); see docs/MIKU_VOICE.md.
No network calls, PyTorch imports or model downloads during a live response.
"""

from concurrent.futures import CancelledError
from dataclasses import replace
import json
import hashlib
import math
import os
import re
import threading

import numpy as np

from .piper_voice import PiperSpeechVoice, _CancellableSession
from .miku_models import model_directory, miku_installed, RESOURCES


def mel_filterbank():
    # librosa.filters.mel(htk=True, norm="slaney", sr=16000, n_fft=1024).
    points = 700 * (10 ** (np.linspace(2595 * np.log10(1 + 30 / 700),
                                       2595 * np.log10(1 + 8000 / 700), 130) / 2595) - 1)
    frequencies = np.linspace(0, 8000, 513)
    lower = (frequencies[None] - points[:-2, None]) / np.diff(points)[:-1, None]
    upper = (points[2:, None] - frequencies[None]) / np.diff(points)[1:, None]
    basis = np.maximum(0, np.minimum(lower, upper)).astype(np.float32)
    basis *= (2 / (points[2:] - points[:-2]))[:, None]
    return basis


_MEL_BASIS = mel_filterbank()
_HANN = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(1024) / 1024)).astype(np.float32)


def log_mel(audio):
    """RMVPE's centered periodic-Hann magnitude STFT and normalized HTK mel."""
    padded = np.pad(audio, (512, 512), mode="reflect")
    frames = np.lib.stride_tricks.sliding_window_view(padded, 1024)[::160]
    magnitude = np.abs(np.fft.rfft(frames * _HANN, axis=-1)).T.astype(np.float32)
    return np.log(np.maximum(_MEL_BASIS @ magnitude, 1e-5))[None].astype(np.float32)


def decode_pitch(salience, threshold=0.03):
    """RMVPE local weighted average over nine bins, retaining unvoiced zeros."""
    centers = salience.argmax(axis=1)
    indices = centers[:, None] + np.arange(-4, 5)[None]
    valid = (indices >= 0) & (indices < 360)
    clipped = np.clip(indices, 0, 359)
    weights = np.take_along_axis(salience, clipped, axis=1) * valid
    cents = (weights * (20 * clipped + 1997.3794084376191)).sum(axis=1)
    cents /= np.maximum(weights.sum(axis=1), 1e-12)
    f0 = (10 * 2 ** (cents / 1200)).astype(np.float32)
    f0[salience.max(axis=1) <= threshold] = 0
    return f0


def coarse_pitch(f0):
    minimum, maximum = 1127 * np.log1p(np.array([50, 1100]) / 700)
    mel = 1127 * np.log1p(f0 / 700)
    bins = np.where(mel > 0, (mel - minimum) * 254 / (maximum - minimum) + 1, mel)
    return np.rint(np.clip(bins, 1, 255)).astype(np.int64)


class MikuConverter:
    """One shared model set for RU/EN, loaded lazily and cancellable in ORT."""

    def __init__(self):
        self._sessions = None
        self._lock = threading.Lock()

    def _load(self, cancelled):
        if self._sessions is not None:
            return
        import onnxruntime as ort
        if not miku_installed():
            raise RuntimeError("Установите Miku в Настройки → Модели. Нужна отдельная модель тембра.")
        root = model_directory()
        metadata = json.loads((root / "miku.json").read_text(encoding="utf-8"))
        if (metadata.get("sample_rate") != 48000 or metadata.get("hop") != 480
                or metadata.get("inter_channels") != 192 or metadata.get("speaker_id") != 0):
            raise RuntimeError("Неподдерживаемая конфигурация Miku. Переустановите голос.")
        sessions = []
        for name in ("contentvec", "rmvpe", "miku"):
            if cancelled.is_set():
                raise CancelledError()
            expected = (metadata["onnx_sha256"] if name == "miku"
                        else RESOURCES[f"{name}.onnx"][1])
            digest = hashlib.sha256()
            with (root / f"{name}.onnx").open("rb") as source:
                while block := source.read(1024 * 1024):
                    if cancelled.is_set():
                        raise CancelledError()
                    digest.update(block)
            if digest.hexdigest() != expected:
                raise RuntimeError(f"Модель Miku ({name}) повреждена. Переустановите голос.")
            options = ort.SessionOptions()
            options.intra_op_num_threads = min(4, os.cpu_count() or 2)
            options.inter_op_num_threads = 1
            sessions.append(ort.InferenceSession(str(root / f"{name}.onnx"),
                            sess_options=options, providers=["CPUExecutionProvider"]))
        if cancelled.is_set():
            raise CancelledError()
        self._sessions = sessions
        self.sample_rate = metadata["sample_rate"]
        self.hop = metadata["hop"]
        self.inter_channels = metadata["inter_channels"]
        self._run_options = ort.RunOptions

    def convert(self, pcm, sample_rate, cancelled):
        if cancelled.is_set():
            raise CancelledError()
        while not self._lock.acquire(timeout=0.05):
            if cancelled.is_set():
                raise CancelledError()
        try:
            from scipy.signal import resample_poly
            self._load(cancelled)
            audio = np.asarray(pcm, dtype=np.float32).reshape(-1)
            if not audio.size or not np.isfinite(audio).all() or sample_rate <= 0:
                raise ValueError("Некорректное аудио для Miku.")
            output_length = round(audio.size * self.sample_rate / sample_rate)
            divisor = math.gcd(int(sample_rate), 16000)
            audio = resample_poly(audio, 16000 // divisor, int(sample_rate) // divisor).astype(np.float32)
            if cancelled.is_set():
                raise CancelledError()
            # Context keeps edge phonemes intact; it is cropped before playback.
            padding = 4000
            # ContentVec loses up to two 10 ms frames at its convolution edges.
            # Extra right context lets us retain the complete final phoneme.
            audio = np.pad(audio, (padding, padding + 320), mode="reflect")
            encoder, predictor, generator = [
                _CancellableSession(session, cancelled, self._run_options) for session in self._sessions
            ]
            features = encoder.run(None, {"input_values": audio[None],
                                         "attention_mask": np.ones((1, audio.size), dtype=np.int64)})[0]
            # RVC's F.interpolate(scale_factor=2) uses nearest-neighbour by default.
            features = np.repeat(features, 2, axis=1)
            mel = log_mel(audio)
            frames = mel.shape[-1]
            mel = np.pad(mel, ((0, 0), (0, 0), (0, (-frames) % 32)))
            salience = predictor.run(None, {"input": mel})[0][0, :frames]
            f0 = decode_pitch(salience) * (2 ** (3 / 12))
            count = min(features.shape[1], f0.size, audio.size // 160)
            rng = np.random.default_rng()
            output = generator.run(None, {
                "phone": features[:, :count].astype(np.float32),
                "lengths": np.array([count], dtype=np.int64),
                "pitch": coarse_pitch(f0[:count])[None], "nsff0": f0[:count][None],
                "sid": np.array([0], dtype=np.int64),
                "noise": rng.standard_normal((1, self.inter_channels, count)).astype(np.float32),
                "source_noise": rng.standard_normal((1, count * self.hop, 1)).astype(np.float32),
            })[0].reshape(-1)
            trim = padding * self.sample_rate // 16000
            output = output[trim:trim + output_length]
            if not output.size or not np.isfinite(output).all():
                raise RuntimeError("Модель Miku вернула некорректный звук.")
            return np.clip(output, -1, 1).astype(np.float32), self.sample_rate
        finally:
            self._lock.release()


class MikuSpeechVoice(PiperSpeechVoice):
    def __init__(self, variant, converter):
        super().__init__(variant)
        self._converter = converter
        self._english = variant.model.espeak_voice.startswith("en")

    def synthesize(self, text, cancelled):
        # English eSpeak reads Miku with /ɪ/; the character's name uses /i/.
        # This changes pronunciation only, never the chat text or stored reply.
        if getattr(self, "_english", False):
            text = re.sub(r"\bMiku\b", "Meekoo", text, flags=re.IGNORECASE)
        chunks = super().synthesize(text, cancelled)
        try:
            for chunk in chunks:
                audio, rate = self._converter.convert(chunk.audio_float_array, chunk.sample_rate, cancelled)
                yield replace(chunk, sample_rate=rate, sample_channels=1, audio_float_array=audio,
                              _audio_int16_array=None, _audio_int16_bytes=None,
                              phoneme_id_samples=None, phoneme_alignments=None, _phoneme_alignments=None)
        finally:
            chunks.close()
