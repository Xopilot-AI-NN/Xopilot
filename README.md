<div align="center">
  <img src="App/assets/icon.png" width="112" alt="Логотип Xopilot" />
  <h1>Xopilot</h1>
  <p><strong>Твой ИИ. Твои проекты. Твои устройства.</strong></p>
  <p>Rust · Dioxus 0.7 · SQLCipher</p>
</div>

Репозиторий переведён на Cargo workspace. Интерфейс и прикладные сервисы написаны на Rust; Python, Flet, Flutter и PyO3 не участвуют в запуске и сборке. Структура `App/app`, `App/settings`, `App/services`, `App/assets` и `Services` сохранена.

**Перенос функциональности ещё не завершён.** Эта версия запускает основное приложение, но не заменяет все возможности Flet-версии. Live, встроенный LiteRT, облако, отдельные защищённые чаты и агент пока недоступны. Подробный статус — [MIGRATION.md](MIGRATION.md). Исходники прежней реализации доступны в истории Git. Старые отчёты в `tests/` относятся к прежней реализации.

## Сейчас доступны

- История чатов, поиск названий и сообщений, переименование, редактирование и удаление сообщений, сохранение черновиков, экспорт Markdown.
- Ответы совместимого Chat Completions API: потоковый текст, отмена запроса, сетевые таймауты. Настраиваются Google AI Studio, OpenRouter или собственный URL. Локальные llama-server и Ollama подключаются тем же способом, их нужно запустить отдельно.
- Вложения: текст/код, PDF, DOCX, JPEG/PNG/WebP/BMP/GIF. Изображения уменьшаются перед отправкой. Неудачное чтение отдельного файла становится пометкой для модели.
- Проекты с инструкциями, привязкой чатов и папкой: список файлов, поиск по коду, Git status и diff --stat, редактор с проверкой внешних изменений.
- Canvas: Markdown, код и изолированный HTML-предпросмотр, сохранение документов. Рисунки прежней версии сохраняются, редактора рисования пока нет.
- Шаблоны запросов, имя, личные инструкции, семь цветовых тем, адаптивная компоновка для узкого экрана.

Внешний API получает историю выбранного чата и прикреплённые к сообщениям материалы. Он не получает всю базу. Локальные материалы и экспортированные Markdown-файлы лежат вне SQLCipher в каталоге данных приложения.

## Интерфейс

Компоновка возвращена к Flet-версии: узкая панель и выдвижное меню, компактный заголовок и ввод, исходные иконки/палитры, сообщения и настройки поверх чата. [Сверка с оригиналом и снимки](previews/FLET_PARITY.md).

## Запуск на Linux

Нужны Rust stable, системные библиотеки WebKitGTK/GTK3 и Dioxus CLI той же версии, что в Cargo.lock.

```bash
# Arch Linux
sudo pacman -S --needed base-devel pkgconf perl gtk3 webkit2gtk-4.1 xdotool

# Debian / Ubuntu с WebKitGTK 4.1
sudo apt-get install build-essential pkg-config perl libgtk-3-dev libwebkit2gtk-4.1-dev libxdo-dev

cargo install dioxus-cli --version 0.7.10 --locked
dx serve --desktop -p xopilot
```

Для сборки приложения вместе со шрифтом и иконкой:

```bash
dx build --desktop -p xopilot --release
# Результат: target/dx/xopilot/release/linux/app/
```

`cargo run -p xopilot` также собирает бинарник, но для упаковки ресурсов используйте `dx`. Настройте API через **Настройки → Модель и API**. Например, у уже запущенного `llama-server` обычно используется `http://127.0.0.1:8080/v1`; в поле модели укажите идентификатор этого сервера. Приложение само не скачивает и не запускает модель.

## Android

Используется тот же Rust-интерфейс с Dioxus Mobile и системным WebView, без Python/Flutter. Настроены прежний application ID `by.xopilot.app`, минимум API 26, INTERNET и Android Keystore. Реальная сборка APK и запуск на устройстве ещё не проверены.

```bash
rustup target add aarch64-linux-android
export JAVA_HOME=/path/to/jdk-17-or-newer
export ANDROID_HOME=/path/to/Android/Sdk
export ANDROID_NDK_HOME="$ANDROID_HOME/ndk/27.2.12479018"

# После установки SDK platform 35, build-tools 35.0.0 и NDK:
dx build --android -p xopilot --no-default-features --features mobile --target aarch64-linux-android
# Для запуска на подключённом устройстве:
dx serve --android -p xopilot --no-default-features --features mobile --target aarch64-linux-android
```

Выбор произвольной папки проекта через Android SAF ещё не реализован: путь должен быть доступен приложению. Для вложений добавлен отдельный системный chooser WebView: данные передаются в Rust блоками по 64 КиБ. Работу с Android content URI необходимо проверить на устройстве. Для обновления старой установки нужна **прежняя подпись APK**: debug-сборка с другим ключом её не заменяет и не получает доступ к прежнему Keystore. Шаблон Dioxus также задаёт versionCode=1; перед выпуском обновления нужен больший код сборки. Автоматической публикации новых релизов пока нет.

## Данные и проверки

Linux использует прежний `$XDG_DATA_HOME/Xopilot` (по умолчанию `~/.local/share/Xopilot`), Windows — `%APPDATA%/Xopilot`. Файл базы — `xopilot.db`. Схема SQLCipher, имена ключей настроек и разрешение ключа шифрования сохранены. При потере ключа приложение показывает ошибку, не создавая новую историю поверх старой. На Android JNI использует прежние `xopilot_keys` / `xopilot.database.v1`; это пока проверено компиляцией JNI-кода, а не обновлением APK на телефоне.

Для отдельного тестового профиля можно задать `XOPILOT_DATA_DIR=/tmp/test/Xopilot`. `XOPILOT_MODELS_DIR` сохраняется как настройка каталога для будущего локального runtime. Обновление неизвестных полей профиля, проектов и Canvas не удаляет их; облачная синхронизация при этом не запускается.

```bash
# Сервисные тесты и рендер Dioxus не требуют графического окружения:
cargo test --workspace --no-default-features --locked
cargo clippy --workspace --all-targets --no-default-features --locked -- -D warnings
cargo fmt --all --check
# С установленными системными зависимостями:
cargo check --workspace --locked
```

## Устройство проекта

```text
Cargo.toml             workspace и общие профили сборки
Dioxus.toml            упаковка и платформы
App/
  main.rs              точка входа
  lib.rs               объявления слоёв
  app/                 окно, меню, чат, Canvas, проекты и тема
  settings/            настройки и персонализация
  services/            прикладная логика и фоновые задачи
  assets/              графика, шрифты и прежние ресурсы
  tests/               интеграционные тесты Rust и рендер интерфейса
Services/
  src/db/              SQLCipher и прежние миграции
  src/security/        ключи шифрования
  tests/               проверки шифрованной истории
scripts/               команды разработки и сборки
```

Разработчик — **DenBroLiik**. Код распространяется по [MIT](LICENSE). Модели, шрифты и сторонние ресурсы имеют собственные лицензии. Сервер и админ-панель развёртываются отдельно; их исходники и секреты в этот репозиторий не входят.
