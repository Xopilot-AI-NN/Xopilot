"""
Файл: App/services/speech_output.py
Разработчик: DenBroLiik
Описание: Озвучка выбранным голосом Live на русском и английском.
    Выбор читается перед каждой репликой; в памяти остаются только модели её профиля.
"""

import re
from concurrent.futures import CancelledError

from .piper_voice import PiperSpeechVoice
from .voice_settings import get_selected_voice, require_voice


def spoken_text(text):
    """Убирает разметку, которую не нужно проговаривать как служебные символы."""
    text = re.sub(r"```.*?```", "Код приведён в чате.", text, flags=re.DOTALL)
    text = re.sub(r"!?\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?m)^\s*(?:#{1,6}\s+|[-*>]\s+)", "", text)
    text = re.sub(r"[`*_]", "", text)
    return text.strip()


def speech_segments(text, last_language="ru"):
    """Язык по предложениям; латинское имя внутри русской фразы не меняет голос."""
    segments = []
    for part in re.split(r"(?<=[.!?])\s+|\n+", text):
        part = part.strip()
        if not part:
            continue
        if re.search(r"[А-Яа-яЁё]", part):
            language = "ru"
        elif re.search(r"[A-Za-z]", part):
            language = "en"
        else:
            language = last_language
        last_language = language
        if segments and segments[-1][0] == language:
            segments[-1] = (language, f"{segments[-1][1]} {part}")
        else:
            segments.append((language, part))
    return segments


class SpeechOutput:
    def __init__(self, voice_id=None):
        self._fixed_voice_id = voice_id
        self._voices = {}
        self._last_language = "ru"
        self.profile = require_voice(voice_id if voice_id is not None else get_selected_voice())
        self.backend = "piper"

    def speak(self, text, cancelled):
        if cancelled.is_set():
            raise CancelledError()
        text = spoken_text(text)
        if not text:
            return
        # Снимок на всю реплику: смена настройки не меняет тембр посреди ответа.
        voice_id = self._fixed_voice_id if self._fixed_voice_id is not None else get_selected_voice()
        profile = require_voice(voice_id)
        if profile.id != self.profile.id:
            self._voices.clear()
            self.profile = profile
        for language, part in speech_segments(text, self._last_language):
            if cancelled.is_set():
                raise CancelledError()
            if language not in self._voices:
                self._voices[language] = PiperSpeechVoice(profile.variant(language))
            if cancelled.is_set():
                raise CancelledError()
            self._voices[language].speak(part, cancelled)
            self._last_language = language
