# Нативные голоса Linux

Xopilot запускает движки отдельными процессами и не требует Python.
Базовый голос: eSpeak NG, русский язык, поставляется в нативном архиве Piper.

Архив движка: rhasspy/piper, выпуск 2023.11.14-2.
Исходники и лицензии компонентов:
- Piper: https://github.com/rhasspy/piper/tree/2023.11.14-2 (MIT).
- eSpeak NG: https://github.com/espeak-ng/espeak-ng (GPL-3.0-or-later).
- ONNX Runtime: https://github.com/microsoft/onnxruntime/tree/v1.14.1 (MIT).
- Piper phonemize: https://github.com/rhasspy/piper-phonemize (MIT; включает eSpeak NG).

Дополнительный голос Руслан пользователь загружает отдельной кнопкой.
Карточка голоса указывает лицензию CC BY-NC-SA 4.0 и набор данных RUSLAN.
Это условия голоса, отдельные от MIT-лицензии исходников Xopilot.
Некоммерческое использование и остальные условия:
https://creativecommons.org/licenses/by-nc-sa/4.0/

Карточка и файлы голоса:
https://huggingface.co/rhasspy/piper-voices/tree/2f358b6a560e3a913ebf509b2f3344f20b367f94/ru/ru_RU/ruslan/medium
