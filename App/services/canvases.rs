// Файл: App/services/canvases.rs
// Описание: Canvas в зашифрованном хранилище; сохраняем неизвестные поля документов.
use super::db::{Store, read_json, write_json};
use anyhow::{Result, ensure};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const KEY: &str = "canvases_v1";

#[derive(Clone, Default, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct Document {
    pub id: String,
    pub title: String,
    pub kind: String,
    pub content: String,
    pub chat_id: Option<i64>,
    pub workspace_id: Option<String>,
    pub updated_at: f64,
    #[serde(flatten)]
    pub extra: BTreeMap<String, serde_json::Value>,
}

/// Возвращает текущее время для метаданных записей.
pub fn now() -> f64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64()
}

/// Восстанавливает документы Canvas, включая неизвестные поля прежних версий.
pub fn list_documents(store: &Store) -> Result<Vec<Document>> {
    store.read(KEY)
}

/// Проверяет и сохраняет документ Canvas с постоянным ID.
pub fn save_document(store: &Store, mut document: Document) -> Result<Document> {
    ensure!(!document.title.trim().is_empty(), "Введите название Canvas");
    ensure!(
        ["text", "code", "web", "drawing"].contains(&document.kind.as_str()),
        "Неизвестный вид Canvas"
    );
    store.with(|db| {
        let mut docs: Vec<Document> = read_json(db, KEY)?;
        if document.id.is_empty() {
            document.id = uuid::Uuid::new_v4().to_string();
        }
        document.updated_at = now();
        docs.retain(|d| d.id != document.id);
        docs.push(document.clone());
        write_json(db, KEY, &docs)?;
        Ok(document)
    })
}

/// Удаляет документ по ID после решения пользователя в интерфейсе.
pub fn delete_document(store: &Store, id: &str) -> Result<()> {
    store.with(|db| {
        let mut docs: Vec<Document> = read_json(db, KEY)?;
        docs.retain(|d| d.id != id);
        write_json(db, KEY, &docs)
    })
}
