// Файл: App/services/drafts.rs
// Описание: Черновики и вложения хранятся вместе с историей.
use super::db::{read_json, write_json};
use advanced_xopilot::db::Database;
use anyhow::Result;
use serde::{Deserialize, Serialize};

#[derive(Clone, Default, Debug, PartialEq, Serialize, Deserialize)]
pub struct Draft {
    #[serde(default)]
    pub text: String,
    #[serde(default)]
    pub files: Vec<(String, String)>,
}

pub fn read_draft(db: &Database, chat_id: i64) -> Result<Draft> {
    read_json(db, &format!("draft:{chat_id}"))
}

pub fn write_draft(db: &Database, chat_id: i64, draft: &Draft) -> Result<()> {
    write_json(db, &format!("draft:{chat_id}"), draft)
}
