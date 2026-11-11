# Проверки Rust / Dioxus — 11 ноября 2026

- `cargo test --workspace --no-default-features --locked`: **43 теста**, ошибок нет.
- `cargo fmt --all --check`: успешно.
- `cargo clippy --workspace --all-targets --no-default-features --locked -- -D warnings`: успешно.
- `cargo clippy --workspace --all-targets --locked -- -D warnings`: успешно с системными GTK3/WebKitGTK/libxdo.
- `dx build --desktop -p xopilot` и `dx build --desktop -p xopilot --example interface_interaction`: успешно, ресурсы упакованы.
- Настоящий WebKitGTK: **56 пользовательских проверок**, ширины 1000 и 390 px, отдельные данные. [Отчёт](UI_REVIEW.md).
- `./scripts/test.sh model /путь/gemma-4-E2B-it.litertlm`: настоящий KV-кеш дополнился, модель сохранила факт из предыдущего сообщения, правка истории пересобрала контекст, сброс чата удалил его. Агент прочитал, изменил и повторно проверил временный файл; содержимое равно `new`.

Тесты проверяют SQLCipher и неверные ключи, сохранение неизвестных JSON-полей, черновики, проекты, шаблоны, Canvas, обработку вложений, очистку Markdown, ограничение путей/симлинков, конфликты редактора, HTTP/SSE и отмену, установку модели с проверкой SHA-256, подтверждения и остановку агента, изоляцию/пароли локальных профилей, изменение имени/аватара без потери памяти.

Настоящий сервер аккаунтов и Google не вызывались. e4b/GPU и физический телефон не испытывались. Подробные команды — [TESTING.md](TESTING.md), ограничения — [MIGRATION.md](../MIGRATION.md).

Android arm64 debug APK пересобран из текущих исходников с JDK 21, NDK 27.2.12479018, платформой SDK 35 и Build Tools 34/35. Через `aapt2` проверены `by.xopilot.app`, versionName 2.1.0, versionCode 1, min SDK 26 / target 35. В APK находятся `lib/arm64-v8a/liblitert-lm.so` и `libmain.so`.

Артефакт: `target/dx/xopilot/debug/android/app/app/build/outputs/apk/debug/app-debug.apk`. Это debug-сборка; установка на телефон, прежняя подпись, Keystore и Android chooser не проверены. Перед выпуском обновления нужен увеличенный versionCode и исходный ключ подписи.
