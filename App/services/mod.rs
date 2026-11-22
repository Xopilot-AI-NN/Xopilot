// Описание: Сервисы приложения по областям ответственности.
// #[path] связывает папки с прежними импортами crate::services::<модуль>.

// Аккаунт, локальный профиль и память пользователя.
#[path = "account/account_deletion.rs"]
pub mod account_deletion;
#[path = "account/cloud_account.rs"]
pub mod cloud_account;
#[path = "account/profile.rs"]
pub mod profile;
#[path = "account/profiles.rs"]
pub mod profiles;
#[path = "account/user_memory.rs"]
pub mod user_memory;

// Агент, протокол инструментов, сеансы и журнал действий.
#[path = "agents/agent.rs"]
pub mod agent;
#[path = "agents/agent_intent.rs"]
pub mod agent_intent;
#[path = "agents/agent_modes.rs"]
pub mod agent_modes;
#[path = "agents/agent_protocol.rs"]
pub mod agent_protocol;
#[path = "agents/agent_session.rs"]
pub mod agent_session;
#[path = "agents/task_history.rs"]
pub mod task_history;

// Генерация ответов, история, черновики и шаблоны чата.
#[path = "chat/api_chat.rs"]
pub mod api_chat;
#[path = "chat/chat_store.rs"]
pub mod chat_store;
#[path = "chat/context_compaction.rs"]
pub mod context_compaction;
#[path = "chat/drafts.rs"]
pub mod drafts;
#[path = "chat/generation.rs"]
pub mod generation;
#[path = "chat/message_navigation.rs"]
pub mod message_navigation;
#[path = "chat/prompt_templates.rs"]
pub mod prompt_templates;
#[path = "chat/ui_session.rs"]
pub mod ui_session;

// Вложения, Canvas, таблицы и экспорт файлов.
#[path = "documents/attachments.rs"]
pub mod attachments;
#[path = "documents/canvases.rs"]
pub mod canvases;
#[path = "documents/exports.rs"]
pub mod exports;
#[path = "documents/office.rs"]
pub mod office;
#[path = "documents/spreadsheets.rs"]
pub mod spreadsheets;

// Разбор изображений, видео и аудио для вложений.
#[path = "media/media.rs"]
pub mod media;
#[path = "media/media_codecs.rs"]
mod media_codecs;

// Модели ИИ: загрузка, импорт, обновления и LiteRT.
#[cfg(target_os = "android")]
#[path = "models/android_downloads.rs"]
pub mod android_downloads;
#[path = "models/compute.rs"]
pub mod compute;
#[path = "models/litert.rs"]
pub mod litert;
#[path = "models/model_import.rs"]
pub mod model_import;
#[path = "models/model_installer.rs"]
pub mod model_installer;
#[path = "models/model_updates.rs"]
pub mod model_updates;

// HTTP-клиент, поиск и чтение веб-страниц.
#[path = "network/http_client.rs"]
pub mod http_client;
#[path = "network/web.rs"]
pub mod web;

// Android, системные диалоги и открытие ссылок.
#[cfg(any(target_os = "android", test))]
#[cfg_attr(test, allow(dead_code))]
#[path = "platform/android.rs"]
pub mod android;
#[cfg(any(target_os = "android", test))]
#[cfg_attr(test, allow(dead_code))]
#[path = "platform/android_exports.rs"]
mod android_exports;
#[path = "platform/mobile_documents.rs"]
pub mod mobile_documents;
#[path = "platform/platform_links.rs"]
pub mod platform_links;

// SQLCipher и каталоги локальных данных.
#[path = "storage/db.rs"]
pub mod db;
#[path = "storage/paths.rs"]
pub mod paths;

// Запуск, фоновые операции, диагностика и обновления приложения.
#[path = "system/diagnostics.rs"]
pub mod diagnostics;
#[path = "system/runtime.rs"]
pub mod runtime;
#[path = "system/startup.rs"]
pub mod startup;
#[path = "system/updates.rs"]
pub mod updates;

// Live, диктовка и платформенные движки озвучивания.
#[path = "voice/live.rs"]
pub mod live;
#[path = "voice/speech.rs"]
pub mod speech;
#[cfg(any(target_os = "android", test))]
#[cfg_attr(test, allow(dead_code))]
#[path = "voice/speech_android.rs"]
mod speech_android;
#[cfg(all(target_os = "linux", feature = "desktop"))]
#[path = "voice/speech_piper.rs"]
pub mod speech_piper;
#[path = "voice/voice.rs"]
pub mod voice;
#[cfg(all(target_os = "linux", feature = "desktop"))]
#[path = "voice/voice_native.rs"]
mod voice_native;

// Рабочие пространства и операции с файлами проекта.
#[path = "workspaces/project_inspection.rs"]
pub mod project_inspection;
#[path = "workspaces/project_tools.rs"]
pub mod project_tools;
#[path = "workspaces/workspaces.rs"]
pub mod workspaces;
