# Голоса Live

В «Настройки → Голос Live» доступны три профиля Xopilot:

| Голос | Характер | Русская модель | Английская модель |
| --- | --- | --- | --- |
| COVE | Мужской, низкий и спокойный | Ruslan | Ryan |
| Miku | Женский, обученный тембр Miku RVC | Irina → Miku RVC | Amy → Miku RVC |
| Maple | Женский, мягкий и спокойный | Irina | LJ Speech |

COVE и Maple используют дикторские модели Piper. Для Miku они задают произношение,
а отдельная обученная RVC-модель переносит речь в тембр Miku. Miku — модель сообщества,
а не официальный голосовой банк Crypton. Русский COVE сохраняет голос Ruslan.
Подробности, источники и образцы: [Miku RVC](../../../../docs/MIKU_VOICE.md).

Выбор хранится в локальной БД (`live_voice`) и применяется со следующего ответа,
включая уже запущенный Live. Текущая реплика заканчивается тем же голосом.
Язык выбирается по предложениям: русский текст → ru, английский → en.
Латинское название внутри русского предложения не переключает голос; числа наследуют
язык предыдущего предложения, а при начале разговора без букв используется русский.

Установка из корня проекта:

```sh
./python/linux/bin/python -m pip install -r App/requirements.txt
./python/linux/bin/python scripts/install_russian_voice.py
```

Историческое имя команды сохранено. По умолчанию устанавливаются пять моделей Piper
(около 316 МБ) и RVC-ресурсы Miku. Профиль Miku занимает около 980 МБ с двумя Piper-моделями;
первый экспорт дополнительно создаёт изолированную среду CPU PyTorch.
Можно установить один профиль, например:

```sh
./python/linux/bin/python scripts/install_russian_voice.py --voice miku
```

В Windows используйте Python окружения проекта. Установщик получает ONNX и JSON
из закреплённой версии репозитория голосов, проверяет SHA-256 и заменяет файлы атомарно.
Повторный запуск пропускает корректные файлы. Общая модель Irina скачивается один раз.
Веса и конфигурации не входят в Git. Старые веса Denis можно хранить отдельно —
они больше не выбираются автоматически.

При обычной работе приложение не скачивает модели и не отправляет реплики в сеть.
При отсутствии нужных файлов или ошибке модели появляется сообщение об ошибке.
Подмена выбранного женского голоса системным мужским синтезатором отключена.
Для COVE/Maple в памяти до двух Piper-моделей; для Miku дополнительно один общий
комплект ContentVec/RMVPE/RVC для обоих языков. Модели загружаются лениво
и повторно используются в разговоре. Смена профиля освобождает прежние модели.
«Перебить» отменяет синтез и воспроизведение.

Параметры в `App/services/voice_catalog.py`: исходная громкость Piper 0,85;
COVE использует `length_scale=1.03`, Miku — 0,92/0,95 для русского/английского,
Maple — 1,03/1,0. Частота проигрывания диктора для Miku больше не изменяется;
конвертер выдаёт аудио 48 кГц и задаёт высоту через F0 модели (+3 полутона).

Источники и сведения из карточек голосов:

- [Ruslan](https://huggingface.co/rhasspy/piper-voices/tree/1162a9173d0ce503555aed757976b7a9912eae4c/ru/ru_RU/ruslan/medium):
  корпус [RUSLAN](https://ruslan-corpus.github.io/), Lenar Gabdrakhmanov, Rustem Garaev,
  Evgenii Razinkov; лицензия набора данных CC BY-NC-SA 4.0.
- [Ryan](https://huggingface.co/rhasspy/piper-voices/tree/1162a9173d0ce503555aed757976b7a9912eae4c/en/en_US/ryan/medium):
  RyanSpeech, лицензия набора данных CC BY-NC-SA 4.0.
- [Irina](https://huggingface.co/rhasspy/piper-voices/tree/1162a9173d0ce503555aed757976b7a9912eae4c/ru/ru_RU/irina/medium):
  RHVoice; карточка указывает лицензию набора данных как Unknown.
- [Amy](https://huggingface.co/rhasspy/piper-voices/tree/1162a9173d0ce503555aed757976b7a9912eae4c/en/en_US/amy/medium):
  карточка отсылает за условиями набора данных к [Mycroft mimic3-voices](https://github.com/MycroftAI/mimic3-voices).
- [LJ Speech](https://huggingface.co/rhasspy/piper-voices/tree/1162a9173d0ce503555aed757976b7a9912eae4c/en/en_US/ljspeech/medium):
  [LJ Speech Dataset](https://keithito.com/LJ-Speech-Dataset/), public domain.
- [Piper](https://github.com/OHF-Voice/piper1-gpl): движок, лицензия GPL-3.0.
