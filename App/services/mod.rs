// Описание: Прикладные сервисы, независимо от интерфейса Dioxus.
pub mod account_deletion;
pub mod agent;
pub mod agent_intent;
pub mod agent_modes;
pub mod agent_protocol;
pub mod agent_session;
#[cfg(any(target_os = "android", test))]
#[cfg_attr(test, allow(dead_code))]
pub mod android;
#[cfg(target_os = "android")]
pub mod android_downloads;
pub mod api_chat;
pub mod attachments;
pub mod canvases;
pub mod chat_store;
pub mod cloud_account;
pub mod compute;
pub mod context_compaction;
pub mod db;
pub mod diagnostics;
pub mod drafts;
pub mod exports;
pub mod generation;
pub mod http_client;
pub mod litert;
pub mod live;
pub mod media;
mod media_codecs;
pub mod message_navigation;
pub mod mobile_documents;
pub mod model_import;
pub mod model_installer;
pub mod model_updates;
pub mod office;
pub mod paths;
pub mod platform_links;
pub mod profile;
pub mod profiles;
pub mod project_inspection;
pub mod project_tools;
pub mod prompt_templates;
pub mod runtime;
pub mod speech;
#[cfg(any(target_os = "android", test))]
#[cfg_attr(test, allow(dead_code))]
mod speech_android;
#[cfg(all(target_os = "linux", feature = "desktop"))]
pub mod speech_piper;
pub mod spreadsheets;
pub mod startup;
pub mod task_history;
pub mod ui_session;
pub mod updates;
pub mod user_memory;
pub mod voice;
#[cfg(all(target_os = "linux", feature = "desktop"))]
mod voice_native;
pub mod web;
pub mod workspaces;
