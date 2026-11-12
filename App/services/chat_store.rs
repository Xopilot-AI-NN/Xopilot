// Файл: App/services/chat_store.rs
// Описание: Навигация и сообщения; прежние таблицы и идентификаторы чатов.
use super::{
    db::Store,
    drafts::{Draft, read_draft},
};
use advanced_xopilot::db::{Database, StoredMessage};
use anyhow::Result;
use serde::{Deserialize, Serialize};

#[derive(
    Clone, Debug, PartialEq, Serialize, Deserialize,
)]
pub struct Chat {
    pub id: i64,
    pub title: String,
    pub count: i64,
}

pub struct Snapshot {
    pub chats: Vec<Chat>,
    pub active: i64,
    pub messages: Vec<StoredMessage>,
    pub draft: Draft,
    pub theme: String,
    pub workspace_name: String,
    pub bookmarks: std::collections::HashSet<i64>,
}

/// Собирает элементы истории с названиями и привязками к проектам.
pub fn list_chat_items(db: &Database) -> Result<Vec<Chat>> {
    Ok(db
        .list_chat_summaries()?
        .into_iter()
        .map(|(id, title, count)| Chat { id, title, count })
        .collect())
}

/// Восстанавливает нужный снимок данных из хранилища.
pub fn load(
    db: &Database,
    requested: Option<i64>,
) -> Result<Snapshot> {
    let mut chats = list_chat_items(db)?;
    if chats.is_empty() {
        db.create_chat("Новый чат")?;
        chats = list_chat_items(db)?;
    }
    let saved = db
        .get_setting("active_chat_id")?
        .and_then(|s| s.parse().ok());
    let active = requested
        .or(saved)
        .filter(|id| chats.iter().any(|c| c.id == *id))
        .unwrap_or(chats[0].id);
    db.set_setting("active_chat_id", &active.to_string())?;
    let spaces: super::workspaces::Workspaces =
        super::db::read_json(db, super::workspaces::KEY)?;
    let workspace_name = spaces
        .chats
        .get(&active.to_string())
        .and_then(|id| {
            spaces.items.iter().find(|w| &w.id == id)
        })
        .map(|w| w.name.clone())
        .unwrap_or_else(|| "Все чаты".into());
    Ok(Snapshot {
        chats,
        active,
        messages: db.get_messages(active)?,
        draft: read_draft(db, active)?,
        theme: db
            .get_setting("theme")?
            .unwrap_or_else(|| "light".into()),
        workspace_name,
        bookmarks: super::message_navigation::marked_in(
            db, active,
        )?,
    })
}

/// Получает снимок чата в фоновой задаче.
pub async fn snapshot(
    store: &Store,
    requested: Option<i64>,
) -> Result<Snapshot> {
    store.run(move |db| load(db, requested)).await
}
