// Описание: Действия связаны с конкретным запросом; журнал не исчезает при смене чата.
use super::db::Store;
use advanced_xopilot::db::StoredMessage;
use anyhow::Result;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
#[derive(Clone, Default, Debug, Serialize, Deserialize, PartialEq)]
#[serde(default)]
pub struct Action {
    pub id: usize,
    pub tool: String,
    pub arguments: Value,
    pub state: String,
    pub output: Value,
    pub seconds: f64,
}
/// Восстанавливает карточки только для сообщений открытого чата.
pub fn load(store: &Store, messages: &[StoredMessage]) -> Result<HashMap<i64, Vec<Action>>> {
    let mut result = HashMap::new();
    for message in messages {
        if message.role == "user" {
            let mut actions: Vec<Action> =
                store.read(&format!("agent_actions_v1:{}", message.id))?;
            for action in &mut actions {
                if matches!(action.state.as_str(), "running" | "approval") {
                    action.state = "interrupted".into();
                }
            }
            if !actions.is_empty() {
                result.insert(message.id, actions);
            }
        }
    }
    Ok(result)
}
/// Записывает завершённые и прерванные шаги в ту же SQLCipher, что и переписку.
pub fn save(store: &Store, message: i64, actions: &[Action]) -> Result<()> {
    store.write(&format!("agent_actions_v1:{message}"), &actions)
}
/// Даёт человеку название действия вместо имени внутренней функции.
pub fn title(tool: &str) -> &str {
    match tool {
        "list_project_files" => "Файлы проекта",
        "read_project_file" => "Чтение файла",
        "write_project_file" => "Изменение файла",
        "search_project" => "Поиск в проекте",
        "run_project_command" => "Запуск команды",
        "git_project" => "Изменения Git",
        "list_canvases" => "Документы Canvas",
        "read_canvas" => "Чтение Canvas",
        "create_canvas" => "Создание Canvas",
        "update_canvas" => "Изменение Canvas",
        "search_memory" => "Поиск в памяти",
        "save_memory" => "Сохранение в память",
        "search_chats" => "Поиск в истории",
        "list_recent_chats" => "Последние чаты",
        "discover_tools" => "Доступные действия",
        _ => "Действие агента",
    }
}
