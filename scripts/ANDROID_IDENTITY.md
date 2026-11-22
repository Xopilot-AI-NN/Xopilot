# Идентификатор Android-приложения

Xopilot использует пакет `by.xopilot.app` и постоянный сертификат из `App/android/signing-certificate.sha256`.

`./scripts/build_android.sh` собирает релиз. `./scripts/build_android.sh --dev-test` создаёт `target/xopilot-dev-test.apk` с тем же именем, ID и ключом подписи. В тестовом режиме доступны WebView DevTools. Прогоны используют отдельную базу в `no_backup/xopilot-dev-test`, отдельные настройки ключей и отдельный alias Android Keystore.

`./scripts/test.sh apk` временно устанавливает dev-сборку и возвращает ранее установленный APK после теста. Обе сборки должны иметь одинаковый versionCode для возврата через ADB. Если Xopilot не установлен, dev-сборка остаётся на устройстве. Удаление основного пакета может уничтожить локальную историю и её ключ Keystore. Копирование папки через ADB не переносит аппаратный ключ.
