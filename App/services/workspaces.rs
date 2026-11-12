// Файл: App/services/workspaces.rs
// Описание: Пространства с инструкциями, папкой и привязкой чатов.
use super::db::{Store, read_json, write_json};
use anyhow::{Result, ensure};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashMap};

pub const KEY: &str = "workspaces_v1";

#[derive(
    Clone, Default, Debug, PartialEq, Serialize, Deserialize,
)]
#[serde(default)]
pub struct Workspace {
    pub id: String,
    pub name: String,
    pub instructions: String,
    #[serde(alias = "folder_path")]
    pub folder: String,
    pub icon: String,
    pub materials: Vec<serde_json::Value>,
    #[serde(flatten)]
    pub extra: BTreeMap<String, serde_json::Value>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct Workspaces {
    pub items: Vec<Workspace>,
    pub chats: HashMap<String, String>,
    pub selected: String,
    #[serde(flatten)]
    pub extra: BTreeMap<String, serde_json::Value>,
}

impl Default for Workspaces {
    /// Задаёт исходное состояние без запущенных действий.
    fn default() -> Self {
        Self {
            items: vec![],
            chats: HashMap::new(),
            selected: "all".into(),
            extra: BTreeMap::new(),
        }
    }
}

/// Читает проекты, сохраняя поля прежних записей.
pub fn list_workspaces(
    store: &Store,
) -> Result<Workspaces> {
    store.with(|db| {
        let mut state: Workspaces = read_json(db, KEY)?;
        for item in &mut state.items {
            if item.folder.is_empty() {
                let access: serde_json::Value = read_json(
                    db,
                    &format!("project_access:{}", item.id),
                )?;
                if access["enabled"].as_bool() == Some(true)
                {
                    item.folder = access["root"]
                        .as_str()
                        .unwrap_or_default()
                        .into();
                }
            }
        }
        Ok(state)
    })
}

/// Проверяет и сохраняет проект вместе с инструкциями и папкой.
pub fn save_workspace(
    store: &Store,
    mut item: Workspace,
) -> Result<()> {
    item.name = item.name.trim().into();
    ensure!(
        !item.name.is_empty(),
        "Введите название пространства"
    );
    if !item.folder.is_empty() {
        ensure!(
            std::path::Path::new(&item.folder).is_dir(),
            "Папка проекта не найдена"
        );
    }
    store.with(|db| {
        let mut state: Workspaces = read_json(db, KEY)?;
        if item.id.is_empty() {
            item.id = uuid::Uuid::new_v4().to_string();
        }
        write_json(
            db,
            &format!("project_access:{}", item.id),
            &serde_json::json!({
                "root": item.folder, "enabled": !item.folder.is_empty(),
            }),
        )?;
        state.items.retain(|w| w.id != item.id);
        state.items.push(item);
        write_json(db, KEY, &state)
    })
}

/// Удаляет пространство, сохраняя его файлы и переписку.
pub fn delete_workspace(
    store: &Store,
    id: &str,
) -> Result<()> {
    store.with(|db| {
        let mut state: Workspaces = read_json(db, KEY)?;
        state.items.retain(|w| w.id != id);
        state.chats.retain(|_, w| w != id);
        if state.selected == id {
            state.selected = "all".into();
        }
        write_json(db, KEY, &state)
    })
}

/// Меняет привязку чата к проекту.
pub fn assign_chat(
    store: &Store,
    chat_id: i64,
    workspace_id: &str,
) -> Result<()> {
    store.with(|db| {
        let mut state: Workspaces = read_json(db, KEY)?;
        ensure!(
            workspace_id == "all"
                || state
                    .items
                    .iter()
                    .any(|w| w.id == workspace_id),
            "Пространство удалено"
        );
        state.chats.insert(
            chat_id.to_string(),
            workspace_id.into(),
        );
        write_json(db, KEY, &state)
    })
}

/// Возвращает инструкции и папку проекта выбранного разговора.
pub fn chat_workspace(
    store: &Store,
    chat_id: i64,
) -> Result<Workspace> {
    let state = list_workspaces(store)?;
    Ok(state
        .chats
        .get(&chat_id.to_string())
        .and_then(|id| {
            state.items.iter().find(|w| &w.id == id)
        })
        .cloned()
        .unwrap_or_default())
}
