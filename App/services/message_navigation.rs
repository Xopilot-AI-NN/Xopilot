// Описание: Закладки совместимы с Flet; в настройках хранятся ID, а не копии переписки.
use super::db::{Store, read_json, write_json};
use anyhow::{Result, ensure};
use serde_json::{Value, json};
use std::collections::{BTreeMap, HashSet};

pub const KEY: &str = "message_bookmarks_v1";

pub fn marked(store: &Store, chat: i64) -> Result<HashSet<i64>> {
    store.with(|db| marked_in(db, chat))
}

pub fn marked_in(db: &advanced_xopilot::db::Database, chat: i64) -> Result<HashSet<i64>> {
    let marks: BTreeMap<String, Value> = read_json(db, KEY)?;
    Ok(marks
        .into_iter()
        .filter(|(_, value)| value["chat_id"].as_i64() == Some(chat))
        .filter_map(|(id, _)| id.parse().ok())
        .collect())
}

pub fn toggle(store: &Store, chat: i64, message: i64) -> Result<bool> {
    store.with(|db| {
        ensure!(
            db.get_messages(chat)?.iter().any(|item| item.id == message),
            "Сообщение больше недоступно"
        );
        let mut marks: BTreeMap<String, Value> = read_json(db, KEY)?;
        let key = message.to_string();
        let saved = if marks.remove(&key).is_some() {
            false
        } else {
            marks.insert(
                key,
                json!({"chat_id":chat,"created_at":super::canvases::now()}),
            );
            true
        };
        write_json(db, KEY, &marks)?;
        Ok(saved)
    })
}
