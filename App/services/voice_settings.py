"""
Файл: App/services/voice_settings.py
Разработчик: DenBroLiik
Описание: Чтение и сохранение голоса Live в настройках локальной БД.
"""

from .db import get_setting, set_setting
from .voice_catalog import DEFAULT_VOICE, VOICES


VOICE_SETTING_KEY = "live_voice"


def get_selected_voice():
    saved = get_setting(VOICE_SETTING_KEY, DEFAULT_VOICE)
    return saved if saved in VOICES else DEFAULT_VOICE


def require_voice(voice_id):
    if voice_id not in VOICES:
        raise ValueError("Неизвестный голос Live.")
    profile = VOICES[voice_id]
    if not profile.installed:
        raise RuntimeError(
            f"Голос {profile.name} не установлен полностью. "
            f"Запустите scripts/install_russian_voice.py --voice {voice_id}."
        )
    return profile


def set_selected_voice(voice_id):
    require_voice(voice_id)
    if not set_setting(VOICE_SETTING_KEY, voice_id):
        raise RuntimeError("Не удалось сохранить голос: локальная база данных недоступна.")
