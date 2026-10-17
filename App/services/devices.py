"""
Файл: /App/services/devices.py
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: Выбор устройств по имени с ленивой загрузкой PortAudio.
"""
import glob
import sys
from .db import get_setting
from .microphone import sd


def _ensure_audio():
    global sd
    if sd is None:
        from . import microphone
        microphone._load_audio()
        sd=microphone.sd


def audio_devices(kind):
    _ensure_audio()
    if sd is None:
        return []
    field = 'max_input_channels' if kind == 'input' else 'max_output_channels'
    return [(d['name'], f"{d['name']} · {sd.query_hostapis(d['hostapi'])['name']}")
            for d in sd.query_devices() if d[field] > 0]


def selected_audio_device(kind):
    _ensure_audio()
    name = get_setting('audio_' + kind, '')
    if not name or sd is None:
        return None
    field = 'max_input_channels' if kind == 'input' else 'max_output_channels'
    for index, device in enumerate(sd.query_devices()):
        if device['name'] == name and device[field] > 0:
            return index
    raise RuntimeError('Выбранное аудиоустройство отключено. Выберите другое в настройках Live.')


def camera_devices():
    if sys.platform.startswith('linux'):
        result = []
        for path in sorted(glob.glob('/dev/video*')):
            index = int(path.removeprefix('/dev/video'))
            try:
                from pathlib import Path
                label = Path(f'/sys/class/video4linux/video{index}/name').read_text().strip()
            except OSError:
                label = 'Камера'
            result.append((str(index), f'{label} ({path})'))
        return result
    return [(str(i), f'Камера {i + 1}') for i in range(4)]
