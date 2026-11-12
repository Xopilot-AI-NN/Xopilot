# Проверки Rust / Dioxus — 11 ноября 2026

- `cargo test --workspace --no-default-features --locked`: **53 теста**, ошибок нет.
- `cargo fmt --all --check`: успешно.
- `cargo clippy --workspace --all-targets --no-default-features --locked -- -D warnings`: успешно.
- `cargo clippy --workspace --all-targets --locked -- -D warnings`: успешно с системными GTK3/WebKitGTK/libxdo.
- `dx build --desktop -p xopilot` и `dx build --desktop -p xopilot --example interface_interaction`: успешно, ресурсы упакованы.
- Настоящий WebKitGTK: **63 пользовательские проверки**, ширины 1000 и 390 px, отдельные данные. [Отчёт](UI_REVIEW.md).
- `./scripts/test.sh model /путь/gemma-4-E2B-it.litertlm`: настоящий KV-кеш дополнился, модель сохранила факт из предыдущего сообщения, правка истории пересобрала контекст, сброс чата удалил его. Агент прочитал, изменил и повторно проверил временный файл; содержимое равно `new`. Настоящий разговор о Canvas также прошёл: документ создан с точным содержимым, веса загружены один раз, KV-кеш дополнен 11 раз. Проверен переход от просьбы о файле к Canvas с тем же текстом и защита от заявления об успехе без квитанции инструмента.

Тесты проверяют SQLCipher и неверные ключи, сохранение неизвестных JSON-полей, черновики, проекты, шаблоны, Canvas, обработку вложений, очистку Markdown, ограничение путей/симлинков, конфликты редактора, HTTP/SSE и отмену, установку модели с проверкой SHA-256, подтверждения и остановку агента, автоматическое создание профиля и постоянство UUID, изменение имени/аватара без потери памяти.

Настоящий сервер аккаунтов и Google не вызывались. e4b/GPU отдельно не испытывались. Проверка POCO X5 5G описана в [ANDROID_DEVICE.md](ANDROID_DEVICE.md). Подробные команды — [TESTING.md](TESTING.md), ограничения — [MIGRATION.md](../MIGRATION.md).

Linux release упакован в dist/linux.zip и отдельный dist/Xopilot. Исполняемый файл запущен из пустого каталога без папки assets: встроенные шрифты, Material Icons и логотип отобразились правильно. Снимок — [rust-standalone.png](../previews/rust-standalone.png).

Android production использует постоянную release-подпись, versionCode 2000013 и отдельный сценарий упаковки. Проверка ./scripts/test.sh apk-check dist/android.apk проверяет 16 КиБ ELF/ZIP-выравнивание. Проверки телефона, фоновой загрузки и восстановления состояния — в [ANDROID_DEVICE.md](ANDROID_DEVICE.md). Старое приложение с другим сертификатом не заменялось.

Workflow проверен actionlint. Установщик закреплённого DX 0.7.10 скачал официальный архив и проверил SHA-256. Результат Linux/Android-сборки локально не заменяет проверку Windows на GitHub Actions.

12 ноября после добавления ADB-стенда, диагностики и OOXML прошли 55 Rust-тестов, форматирование и Clippy. Linux WebKitGTK прошёл 82 UI-проверки, включая общий с APK модуль. Отдельный APK прошёл 25 проверок на POCO X5 5G. JSON-отчёты находятся в ui-review-results.json и android-ui-results.json.
