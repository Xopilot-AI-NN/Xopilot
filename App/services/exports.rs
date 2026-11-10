// Описание: Экспорт чата; API-ключи и настройки в файл не попадают.
use advanced_xopilot::db::StoredMessage;
use anyhow::Result;
use std::path::PathBuf;

pub fn markdown(title: &str, messages: &[StoredMessage]) -> String {
    let mut out = format!("# {title}\n\n");
    for message in messages {
        out.push_str(if message.role == "user" {
            "## Вы\n\n"
        } else {
            "## Xopilot\n\n"
        });
        out.push_str(&message.content);
        for (name, _) in &message.attachments {
            out.push_str(&format!("\n\nВложение: {name}"));
        }
        out.push_str("\n\n");
    }
    out
}

pub fn save_markdown(title: &str, messages: &[StoredMessage]) -> Result<PathBuf> {
    let dir = super::paths::app_data_dir()?.join("exports");
    std::fs::create_dir_all(&dir)?;
    let path = dir.join(format!("chat-{}.md", uuid::Uuid::new_v4()));
    std::fs::write(&path, markdown(title, messages))?;
    Ok(path)
}
