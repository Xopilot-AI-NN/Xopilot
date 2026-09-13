# Голоса Live

В «Настройки → Голос Live» доступны три профиля Xopilot:

| Голос | Характер | Русская модель | Английская модель |
| --- | --- | --- | --- |
| COVE | Мужской, низкий и спокойный | Ruslan | Ryan |
| Miku | Женский, высокий и лёгкий | Irina, повышенная высота | Amy |
| Maple | Женский, мягкий и спокойный | Irina, слегка пониженная высота | LJ Speech |

Это названия локальных профилей Xopilot. Русские Miku и Maple используют одну
женскую модель с разными высотой и темпом. Между языками используются разные дикторы.
Русский COVE сохраняет ранее выбранный голос Ruslan и его параметры.

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

Историческое имя команды сохранено. По умолчанию устанавливаются все пять моделей
для трёх профилей (около 316 МБ в сумме). Можно установить один профиль, например:

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
В памяти остаётся не больше двух моделей текущего профиля; они загружаются лениво
и повторно используются в разговоре. Смена профиля освобождает прежние модели.
«Перебить» отменяет и синтез, и воспроизведение.

Параметры в `App/services/voice_catalog.py`: громкость всех голосов 0,85; COVE
использует `length_scale=1.03`, без изменения высоты. Для Miku ru/en частота
воспроизведения умножается на 1,10/1,06, темп синтеза — 1,05/1,03;
для Maple ru — 0,97 и 1,03, для Maple en — исходная высота и темп.

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
