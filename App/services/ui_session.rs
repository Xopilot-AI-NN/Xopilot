// Описание: Минимальный снимок навигации хранится в SQLCipher, а не в открытом файле.
// Android вправе удалить фоновый процесс. Поэтому одного Signal или WebView history недостаточно.
// Не восстанавливаем разрешения агента и не продолжаем незавершённые команды автоматически:
// они остаются в журнале действий и после прерывания требуют нового решения пользователя.
use super::db::{Store, read_json};
use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(
    Clone,
    Copy,
    PartialEq,
    Default,
    Debug,
    Serialize,
    Deserialize,
)]
#[serde(rename_all = "snake_case")]
pub enum Screen {
    #[default]
    Chat,
    Settings,
    Workspaces,
    Canvas,
    Templates,
    Chats,
    Materials,
    Private,
    Model,
    Api,
    Account,
    Memory,
}

#[derive(
    Clone, Default, PartialEq, Serialize, Deserialize,
)]
#[serde(default)]
pub struct Session {
    pub screen: Screen,
    pub settings_section: Option<usize>,
    pub sidebar: bool,
    pub history: Vec<Screen>,
    pub scrolls: HashMap<String, f64>,
    pub chat_scroll: f64,
}

/// Восстанавливает только ограниченный снимок; ошибки старого UI не блокируют саму историю.
pub fn load(store: &Store) -> Result<Session> {
    store.with(|db| {
        let mut value: Session =
            read_json(db, "ui_session_v1")
                .unwrap_or_default();
        value.settings_section = value
            .settings_section
            .filter(|section| *section < 6);
        value.history.truncate(16);
        value.scrolls.retain(|key, value| {
            key.len() < 100 && value.is_finite()
        });
        if !value.chat_scroll.is_finite() {
            value.chat_scroll = 0.0;
        }
        Ok(value)
    })
}

/// Записывает навигацию вместе с черновиком в одной транзакции перед сворачиванием.
/// Используем существующую атомарную запись settings, не меняя схему и ключи прежней истории.
/// Если приложение прервётся посреди записи, SQLite оставит целым предыдущий снимок.
pub fn save(
    store: &Store,
    session: &Session,
    active: Option<i64>,
    draft: &super::drafts::Draft,
) -> Result<()> {
    store.with(|db| {
        let mut updates = vec![(
            "ui_session_v1".into(),
            serde_json::to_string(session)?,
        )];
        if let Some(id) = active {
            updates.push((
                format!("draft:{id}"),
                serde_json::to_string(draft)?,
            ));
        }
        db.apply_sync_settings(&[], &updates)?;
        Ok(())
    })
}
