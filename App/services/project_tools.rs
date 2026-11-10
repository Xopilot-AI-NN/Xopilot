// Описание: Сохранение редактора с проверкой внешних изменений.
use super::project_inspection::{read_text, resolve};
use anyhow::{Result, ensure};
use sha2::{Digest, Sha256};
use std::path::Path;

pub fn fingerprint(text: &str) -> String {
    hex::encode(Sha256::digest(text.as_bytes()))
}

pub fn save_existing(root: &Path, path: &str, content: &str, original: &str) -> Result<String> {
    let full = resolve(root, path)?;
    ensure!(
        fingerprint(&read_text(root, path)?) == original,
        "Файл изменён извне. Откройте его заново перед сохранением"
    );
    ensure!(
        content.len() <= super::project_inspection::MAX_FILE as usize,
        "Файл больше 1 МиБ"
    );
    // Пишем соседний файл, затем атомарно заменяем исходник.
    let temp = full.with_file_name(format!(".xopilot-{}.tmp", uuid::Uuid::new_v4()));
    let result = (|| -> Result<()> {
        use std::io::Write;
        let permissions = full.metadata()?.permissions();
        let mut file = std::fs::OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(&temp)?;
        file.write_all(content.as_bytes())?;
        file.set_permissions(permissions)?;
        file.sync_all()?;
        ensure!(
            fingerprint(&read_text(root, path)?) == original,
            "Файл изменён во время сохранения"
        );
        std::fs::rename(&temp, &full)?;
        Ok(())
    })();
    if result.is_err() {
        let _ = std::fs::remove_file(&temp);
    }
    result?;
    Ok(fingerprint(content))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn external_change_is_preserved() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("main.rs");
        std::fs::write(&path, "old").unwrap();
        let original = fingerprint("old");
        std::fs::write(&path, "external").unwrap();
        assert!(save_existing(dir.path(), "main.rs", "mine", &original).is_err());
        assert_eq!(std::fs::read_to_string(&path).unwrap(), "external");
    }
}
