# Зависимости: проверка безопасности 24 октября 2026

Исполнитель: Codex. Полный запрос (все 112 GitHub alerts): **blocked** до сверки с авторизованным списком Dependabot. GitHub CLI не авторизован, браузер недоступен; предупреждения вручную не закрывались. Ниже приведены проверенные изменения локального checkout.

## Исправления

| Пакет | Объявлено до | После | Advisory до обновления |
|---|---|---|---|
| Pillow | 12.3.0 | 13.0.0 | 37 |
| pypdf | 6.20.0 | 6.21.2 | 9 |
| filelock | 4.1.0 | 4.2.1 | 6 |
| ctutils (Rust) | 0.4.2 | 0.4.4 | RUSTSEC-2026-0385 |

Python-манифесты App/requirements.txt и pyproject.toml согласованы, включая Android-маркеры. Требование Python поднято с >=3.10 до >=3.11 согласно метаданным Pillow 13.0.0. Расширение flet-xopilot-mobile имеет отдельную политику Python и не менялось.

Уязвимые операции достижимы через обработку растровых вложений, аватарок и миниатюр, чтение PDF и библиотечные файловые блокировки. ctutils приходит через sha2/digest и Linux keyring/secret-service. Стратегия — обновление общего библиотечного слоя, без изменения прикладных контрактов и форматов данных.

Android: изменены версии и проверка реальных метаданных колёс/APK; SHA256 исходника Pillow сверена с PyPI. Патч закреплённого Forge адаптирован к setup.py Pillow 13. Кеш CI и локальный кеш учитывают SHA256 патча; отсутствие/подмена provenance вызывает пересборку с --clean. Support wheels заново подготавливаются и для ранее отсутствовавшей ABI.

Изменены: App/requirements.txt, pyproject.toml, Services/Cargo.lock, .github/workflows/build.yml, scripts/build_android_wheels.py, scripts/verify_android_apk.py, scripts/patches/pillow-13-android.patch, tests/test_android_dependencies.py. Остальные локальные изменения существовали до этой задачи.

## Проверки по порядку

1. Синтаксис изменённых Python-файлов, диагностика редактора и git diff --check: успешно. Патч Android применяется к проверенному исходнику Pillow 13.0.0 без fuzz и смещений.
2. pip-audit 2.10.1 -r App/requirements.txt --format json: до обновления 52 advisory в 3 пакетах; после обновления 40 разрешённых пакетов, 0 известных уязвимостей, 0 пропущенных пакетов. Это проверка известных диапазонов версий; реальные повреждающие память PoC не запускались.
3. OSV querybatch для всех 257 registry-пакетов Services/Cargo.lock: ctutils advisory после обновления отсутствует. Остались четыре информационных сообщения unmaintained: anymap2, zbus_names, zvariant, zvariant_derive. Они не были подавлены или объявлены исправленными; переход требует обновления родительских зависимостей.
4. python/linux/bin/python -m unittest discover -s tests -v: 628 тестов за 63.535 с, 612 успешно, 16 пропущены. После изменения кеша отдельно python/linux/bin/python -m unittest discover -s tests -p test_android_dependencies.py -q: 5 успешно, включая новую регрессию устаревшего/отсутствующего/повреждённого provenance.
5. cargo test --manifest-path Services/Cargo.toml --lib --release --locked: 4 успешно. Cargo.lock обновлён штатным cargo update -p ctutils --precise 0.4.4.
6. python/linux/bin/python scripts/build_android_wheels.py: успешно после исправления подготовки support wheels. Чистая сборка Pillow 13.0.0 и cryptography 50.0.2 для arm64-v8a/x86_64 завершена; проверены метаданные всех шести колёс (включая OpenSSL 3.5.7), ABI и выравнивание ELF 16 KiB всех 14 нативных библиотек. Повторный запуск успешно использовал кеш с совпадающим SHA256 патча. SHA256 исходников, патча и готовых колёс записаны в build/android-wheels/provenance.json. Первоначальная попытка остановилась на отсутствующем OpenSSL support wheel для x86_64, поэтому успешной считается повторная сборка с исправленной подготовкой.

Обычные сценарии сохранены тестами PNG/JPEG/WebP/BMP/GIF, аватарок, экспорта документов с кириллицей, PDF, файловых блокировок и синхронизации. Тесты недоверенных сигнатур подтверждают отказ выбирать запрещённые декодеры; старый Pillow 12.3.0 отклоняется проверкой Android-метаданных.

## Ограничения

- Список 112 alerts GitHub и их состояние после отправки в основную ветку не проверены. Число локальных advisory не равно числу GitHub alerts: один advisory может относиться к нескольким манифестам.
- Полный прогон использовал локальный Flet 1.0.3; в манифестах уже был Flet 1.0.4. Все три изменённые Python-библиотеки реально установлены в проверенных версиях.
- pip check сообщает о прежнем конфликте локального flet-audio-recorder 0.86.5 с Flet 1.0.3. Этот пакет отсутствует в манифестах и не импортируется приложением; он не удалялся.
- Python 3.11 отдельно не запускался; проверена основная среда Python 3.14. Полная APK и физическое устройство этим изменением пока не проверены.
- Изменения не опубликованы; существующие APK/установки сами от редактирования манифестов не обновляются.

## Найденные Python advisory и версии исправлений

### pillow

- CVE-2026-112895, [GHSA-p4wg-p73j-c528](https://github.com/advisories/GHSA-p4wg-p73j-c528); исправлено в 13.0.0.
- CVE-2026-112400, [GHSA-65qm-jvmh-6pqg](https://github.com/advisories/GHSA-65qm-jvmh-6pqg); исправлено в 13.0.0.
- CVE-2026-112397, [GHSA-58r4-6rv3-gfh8](https://github.com/advisories/GHSA-58r4-6rv3-gfh8); исправлено в 13.0.0.
- CVE-2026-112896, [GHSA-pchr-8j38-3x4p](https://github.com/advisories/GHSA-pchr-8j38-3x4p); исправлено в 13.0.0.
- CVE-2026-112897, [GHSA-q45j-58j2-45rg](https://github.com/advisories/GHSA-q45j-58j2-45rg); исправлено в 13.0.0.
- CVE-2026-112395, [GHSA-462x-pgg6-55fp](https://github.com/advisories/GHSA-462x-pgg6-55fp); исправлено в 13.0.0.
- CVE-2026-112404, [GHSA-c6hw-5grf-ff96](https://github.com/advisories/GHSA-c6hw-5grf-ff96); исправлено в 13.0.0.
- CVE-2026-112899, [GHSA-vx6w-vv9f-6gvg](https://github.com/advisories/GHSA-vx6w-vv9f-6gvg); исправлено в 13.0.0.
- CVE-2026-112402, [GHSA-7mwm-ghpf-9vrm](https://github.com/advisories/GHSA-7mwm-ghpf-9vrm); исправлено в 13.0.0.
- CVE-2026-112900, [GHSA-w889-685w-c8fh](https://github.com/advisories/GHSA-w889-685w-c8fh); исправлено в 13.0.0.
- CVE-2026-112893, [GHSA-j4m9-6w36-pw47](https://github.com/advisories/GHSA-j4m9-6w36-pw47); исправлено в 13.0.0.
- CVE-2026-112392, [GHSA-27h8-gf7j-v5hc](https://github.com/advisories/GHSA-27h8-gf7j-v5hc); исправлено в 13.0.0.
- CVE-2026-112891, [GHSA-fc9g-5qg7-mf45](https://github.com/advisories/GHSA-fc9g-5qg7-mf45); исправлено в 13.0.0.
- CVE-2026-112405, [GHSA-cp9v-662q-vvx9](https://github.com/advisories/GHSA-cp9v-662q-vvx9); исправлено в 13.0.0.
- CVE-2026-112390, [GHSA-22hg-r758-rrw9](https://github.com/advisories/GHSA-22hg-r758-rrw9); исправлено в 13.0.0.
- CVE-2026-112401, [GHSA-74r2-7ff9-mjj2](https://github.com/advisories/GHSA-74r2-7ff9-mjj2); исправлено в 13.0.0.
- CVE-2026-112901, [GHSA-xgh8-jp6q-p5x8](https://github.com/advisories/GHSA-xgh8-jp6q-p5x8); исправлено в 13.0.0.
- CVE-2026-112391, [GHSA-254f-3936-288h](https://github.com/advisories/GHSA-254f-3936-288h); исправлено в 13.0.0.
- CVE-2026-112894, [GHSA-jg86-v3jv-hrpm](https://github.com/advisories/GHSA-jg86-v3jv-hrpm); исправлено в 13.0.0.
- CVE-2026-112406, [GHSA-f2g6-542v-9j58](https://github.com/advisories/GHSA-f2g6-542v-9j58); исправлено в 13.0.0.
- CVE-2026-112399, [GHSA-5xm2-6676-qcp9](https://github.com/advisories/GHSA-5xm2-6676-qcp9); исправлено в 13.0.0.
- CVE-2026-112892, [GHSA-gg2r-wvfm-q9rx](https://github.com/advisories/GHSA-gg2r-wvfm-q9rx); исправлено в 13.0.0.
- CVE-2026-112393, [GHSA-332p-7hrc-92wf](https://github.com/advisories/GHSA-332p-7hrc-92wf); исправлено в 13.0.0.
- CVE-2026-112396, [GHSA-4rr5-89j8-mwwm](https://github.com/advisories/GHSA-4rr5-89j8-mwwm); исправлено в 13.0.0.
- CVE-2026-96638, [GHSA-24rc-8hj2-v98c](https://github.com/advisories/GHSA-24rc-8hj2-v98c); исправлено в 13.0.0.
- CVE-2026-96641, [GHSA-4rm8-3hmm-39fg](https://github.com/advisories/GHSA-4rm8-3hmm-39fg); исправлено в 13.0.0.
- CVE-2026-96640, [GHSA-mrfp-p49p-3hf2](https://github.com/advisories/GHSA-mrfp-p49p-3hf2); исправлено в 13.0.0.
- CVE-2026-96642, [GHSA-3j72-p6qg-6xp7](https://github.com/advisories/GHSA-3j72-p6qg-6xp7); исправлено в 13.0.0.
- CVE-2026-96639, [GHSA-v9pv-5gc8-w2m6](https://github.com/advisories/GHSA-v9pv-5gc8-w2m6); исправлено в 13.0.0.
- CVE-2026-96643, [GHSA-g4qv-2jxx-769h](https://github.com/advisories/GHSA-g4qv-2jxx-769h); исправлено в 13.0.0.
- CVE-2026-96637, [GHSA-g842-9rc4-69pw](https://github.com/advisories/GHSA-g842-9rc4-69pw); исправлено в 13.0.0.
- CVE-2026-96644, [GHSA-9v9v-9qvf-h2hj](https://github.com/advisories/GHSA-9v9v-9qvf-h2hj); исправлено в 13.0.0.
- CVE-2026-96778, [GHSA-g7cr-3p24-7wf7](https://github.com/advisories/GHSA-g7cr-3p24-7wf7); исправлено в 13.0.0.
- CVE-2026-96636, [GHSA-p8hx-v2p6-rp84](https://github.com/advisories/GHSA-p8hx-v2p6-rp84); исправлено в 13.0.0.
- [GHSA-78g4-xqwv-q3g8](https://github.com/advisories/GHSA-78g4-xqwv-q3g8); исправлено в 13.0.0.
- CVE-2026-114501, [GHSA-654x-cwwv-5j9c](https://github.com/advisories/GHSA-654x-cwwv-5j9c); исправлено в 13.0.0.
- CVE-2026-112398, [GHSA-5x8w-8jj5-q52h](https://github.com/advisories/GHSA-5x8w-8jj5-q52h); исправлено в 13.0.0.

### pypdf

- CVE-2026-113792, [GHSA-qfv9-64jg-mh7p](https://github.com/advisories/GHSA-qfv9-64jg-mh7p); исправлено в 6.20.1.
- CVE-2026-113793, [GHSA-9mx8-4j7g-633p](https://github.com/advisories/GHSA-9mx8-4j7g-633p); исправлено в 6.20.1.
- CVE-2026-113786, [GHSA-5hx5-vpf9-5wcv](https://github.com/advisories/GHSA-5hx5-vpf9-5wcv); исправлено в 6.21.1.
- CVE-2026-113791, [GHSA-cgf9-327m-v77c](https://github.com/advisories/GHSA-cgf9-327m-v77c); исправлено в 6.21.0.
- CVE-2026-113790, [GHSA-f54x-cmq8-qg57](https://github.com/advisories/GHSA-f54x-cmq8-qg57); исправлено в 6.21.0.
- CVE-2026-113789, [GHSA-6vvc-x485-93v7](https://github.com/advisories/GHSA-6vvc-x485-93v7); исправлено в 6.21.0.
- CVE-2026-115572, [GHSA-6c7f-9265-g8fw](https://github.com/advisories/GHSA-6c7f-9265-g8fw); исправлено в 6.21.2.
- CVE-2026-115585, [GHSA-jr96-gvgh-j3r4](https://github.com/advisories/GHSA-jr96-gvgh-j3r4); исправлено в 6.21.2.
- CVE-2026-115580, [GHSA-gmh7-3g9r-mjh5](https://github.com/advisories/GHSA-gmh7-3g9r-mjh5); исправлено в 6.21.2.

### filelock

- CVE-2026-112906, [GHSA-2g95-wg33-c5x2](https://github.com/advisories/GHSA-2g95-wg33-c5x2); исправлено в 4.2.1.
- CVE-2026-112940, [GHSA-v4x8-3wr5-3wq8](https://github.com/advisories/GHSA-v4x8-3wr5-3wq8); исправлено в 4.2.1.
- CVE-2026-112914, [GHSA-crv4-6mhj-j5jh](https://github.com/advisories/GHSA-crv4-6mhj-j5jh); исправлено в 4.2.1.
- CVE-2026-112913, [GHSA-9vhv-jxww-xfm5](https://github.com/advisories/GHSA-9vhv-jxww-xfm5); исправлено в 4.2.1.
- CVE-2026-112937, [GHSA-jqc4-5cvw-7w85](https://github.com/advisories/GHSA-jqc4-5cvw-7w85); исправлено в 4.2.1.
- CVE-2026-112907, [GHSA-567q-5qvw-pf92](https://github.com/advisories/GHSA-567q-5qvw-pf92); исправлено в 4.2.1.

