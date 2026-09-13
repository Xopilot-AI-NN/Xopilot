"""
Файл: App/services/voice_catalog.py
Разработчик: DenBroLiik
Описание: Три голоса Xopilot и закреплённые локальные модели для русского и английского.
    Каталог не импортирует БД или нативные библиотеки; его использует и установщик.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


VOICE_DIR = Path(__file__).resolve().parents[1] / "data" / "models" / "tts"
REVISION = "1162a9173d0ce503555aed757976b7a9912eae4c"
DEFAULT_VOICE = "cove"


@dataclass(frozen=True)
class VoiceModel:
    name: str
    directory: str
    sha256: str
    config_sha256: str
    espeak_voice: str

    @property
    def path(self):
        return VOICE_DIR / f"{self.name}.onnx"

    @property
    def config_path(self):
        return VOICE_DIR / f"{self.name}.onnx.json"

    @property
    def installed(self):
        return self.path.is_file() and self.config_path.is_file()


MODELS = {
    "ruslan": VoiceModel(
        "ru_RU-ruslan-medium", "ru/ru_RU/ruslan/medium",
        "72a5f88e0b20928064eb45d88e1daa21f8af62d18613580d32cbb4aed48dcf7f",
        "706a4fb17bc304abd07809b552deae615e64dcbffbfbd09854ba37ca59e88117", "ru",
    ),
    "irina": VoiceModel(
        "ru_RU-irina-medium", "ru/ru_RU/irina/medium",
        "8ff38212d23da300bbe3705c645e6e5b9475f0bfde01558eb17813e22acaaaaa",
        "c2ec28bb38e2b59e93b959b3e40348c1afebbd272f30fed5d41205d08e98a9d7", "ru",
    ),
    "ryan": VoiceModel(
        "en_US-ryan-medium", "en/en_US/ryan/medium",
        "abf4c274862564ed647ba0d2c47f8ee7c9b717d27bdad9219100eb310db4047a",
        "44034c056cb15681b2ad494307c7f3f2e4499d1253c700c711fa0a4607ffe78d", "en-us",
    ),
    "amy": VoiceModel(
        "en_US-amy-medium", "en/en_US/amy/medium",
        "b3a6e47b57b8c7fbe6a0ce2518161a50f59a9cdd8a50835c02cb02bdd6206c18",
        "95a23eb4d42909d38df73bb9ac7f45f597dbfcde2d1bf9526fdeaf5466977d77", "en-us",
    ),
    "ljspeech": VoiceModel(
        "en_US-ljspeech-medium", "en/en_US/ljspeech/medium",
        "6f52a751e2349abe7a76735eb09dc1875298c77ea2342ffd2fef79ff81b87f22",
        "141d612cc0a95ed7efc1ca936b845c2364967f2e9217c5dbfcf69fc4d6c65860", "en",
    ),
}


@dataclass(frozen=True)
class VoiceVariant:
    model_key: str
    length_scale: float = 1.03
    rate_scale: float = 1.0
    # None — использовать значение по умолчанию из .onnx.json самой модели.
    noise_scale: Optional[float] = None
    noise_w_scale: Optional[float] = None

    @property
    def model(self):
        return MODELS[self.model_key]


@dataclass(frozen=True)
class VoiceProfile:
    id: str
    name: str
    gender: str
    description: str
    ru: VoiceVariant
    en: VoiceVariant

    def variant(self, language):
        if language not in {"ru", "en"}:
            raise ValueError("Поддерживаются русский и английский языки.")
        return getattr(self, language)

    @property
    def installed(self):
        return self.ru.model.installed and self.en.model.installed


# Как отличаются голоса друг от друга без «бурундука» и без «бабули»:
#  - length_scale (родной параметр Piper) — темп. Безопасен, используем как основной рычаг.
#  - noise_w_scale (тоже родной параметр Piper) — вариативность длительности фонем: больше —
#    живее/энергичнее звучание, меньше — ровнее/спокойнее (именно этот параметр,
#    а не медленный темп, делает en_US-ljspeech спокойным, а не «старческим»).
#  - rate_scale (наш собственный питч-трюк через смену sample_rate при проигрывании)
#    держим в минимуме и только там, где иначе нечем отличить голос (для RU есть
#    только один женский голос — irina) — больше ~6-7% уже звучит как «бурундук».
VOICES = {
    "cove": VoiceProfile("cove", "COVE", "Мужской", "Низкий, спокойный",
                         VoiceVariant("ruslan"), VoiceVariant("ryan")),
    "miku": VoiceProfile("miku", "Miku", "Женский", "Высокий, лёгкий",
                         VoiceVariant("irina", length_scale=0.92, rate_scale=1.06, noise_w_scale=1.0),
                         VoiceVariant("amy", length_scale=0.95)),
    "maple": VoiceProfile("maple", "Maple", "Женский", "Мягкий, спокойный",
                          VoiceVariant("irina", length_scale=1.03, noise_w_scale=0.45),
                          VoiceVariant("ljspeech", length_scale=1.0)),
}