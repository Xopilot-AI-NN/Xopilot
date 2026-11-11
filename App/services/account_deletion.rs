// Описание: Завершаем уже подтверждённое удаление данных прежней версией до открытия БД.
use anyhow::{Result, ensure};
use std::path::Path;

/// Исполняет ранее подтверждённый локальный маркер удаления до открытия базы.
pub fn perform_pending_erasure(root: &Path) -> Result<bool> {
    let marker = root.join(".erase-personal-data");
    if !marker.is_file() {
        return Ok(false);
    }
    ensure!(
        root.file_name().is_some_and(|n| n == "Xopilot") && !root.is_symlink(),
        "Небезопасный каталог удаления данных"
    );
    for entry in std::fs::read_dir(root)? {
        let entry = entry?;
        if entry.file_name() == ".erase-personal-data" {
            continue;
        }
        if entry.file_type()?.is_dir() {
            std::fs::remove_dir_all(entry.path())?;
        } else {
            std::fs::remove_file(entry.path())?;
        }
    }
    // Маркер остаётся при любой промежуточной ошибке: очистка продолжится при перезапуске.
    std::fs::remove_file(marker)?;
    Ok(true)
}

#[cfg(test)]
mod tests {
    use super::*;
    /// Проверяет маркер удаления и сохранность файлов вне данных приложения.
    #[test]
    fn erasure_requires_a_previous_marker_and_keeps_external_files() {
        let temp = tempfile::tempdir().unwrap();
        let root = temp.path().join("Xopilot");
        std::fs::create_dir(&root).unwrap();
        std::fs::write(root.join("history"), "private").unwrap();
        assert!(!perform_pending_erasure(&root).unwrap());
        std::fs::write(root.join(".erase-personal-data"), "approved").unwrap();
        std::fs::write(temp.path().join("external"), "keep").unwrap();
        assert!(perform_pending_erasure(&root).unwrap());
        assert_eq!(std::fs::read_dir(root).unwrap().count(), 0);
        assert!(temp.path().join("external").exists());
    }
}
