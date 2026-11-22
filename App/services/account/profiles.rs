// Описание: Статистика автоматически созданного профиля, без регистрации и паролей.
use super::{db::Store, paths};
use anyhow::Result;
use std::path::Path;
#[derive(Clone, Default)]
pub struct Usage {
    pub chats: usize,
    pub messages: i64,
    pub bytes: u64,
    pub cached_cloud: bool,
}
/// Подсчитывает чаты, сообщения и размер данных профиля без весов моделей и runtime.
pub fn usage(store: &Store, root: &Path) -> Result<Usage> {
    let (chats, messages, cached_cloud) =
        store.with(|db| {
            Ok((
                db.list_chats()?.len(),
                db.total_message_count()?,
                db.get_setting("cloud_account_v1")?
                    .is_some(),
            ))
        })?;
    let mut bytes = 0u64;
    let mut pending = vec![root.to_path_buf()];
    let mut count = 0;
    while let Some(dir) = pending.pop() {
        if let Ok(entries) = std::fs::read_dir(dir) {
            for entry in entries.flatten() {
                if root == paths::base_data_dir()?.as_path()
                    && entry.path().parent() == Some(root)
                    && ["accounts", "models", "runtime"]
                        .contains(
                            &entry
                                .file_name()
                                .to_string_lossy()
                                .as_ref(),
                        )
                {
                    continue;
                }
                count += 1;
                if count > 100_000 {
                    break;
                }
                let kind = entry.file_type()?;
                if kind.is_dir() {
                    pending.push(entry.path());
                } else if kind.is_file() {
                    bytes = bytes.saturating_add(
                        entry.metadata()?.len(),
                    );
                }
            }
        }
    }
    Ok(Usage {
        chats,
        messages,
        bytes,
        cached_cloud,
    })
}
