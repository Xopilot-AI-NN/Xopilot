// Описание: Прикладные сервисы, независимо от интерфейса Dioxus.
pub mod account_deletion;
#[cfg(any(target_os = "android", test))]
#[cfg_attr(test, allow(dead_code))]
pub mod android;
pub mod api_chat;
pub mod attachments;
pub mod canvases;
pub mod chat_store;
pub mod db;
pub mod drafts;
pub mod exports;
pub mod mobile_documents;
pub mod paths;
pub mod profile;
pub mod project_inspection;
pub mod project_tools;
pub mod prompt_templates;
pub mod runtime;
pub mod workspaces;
