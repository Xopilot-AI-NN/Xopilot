// Файл: App/services/paths.rs
// Описание: Доступные для записи каталоги, совместимые с прежней установкой.
use anyhow::{Context, Result};
use std::path::PathBuf;

pub fn base_data_dir() -> Result<PathBuf> {
    if let Some(path) = std::env::var_os("XOPILOT_DATA_DIR") {
        return Ok(PathBuf::from(path));
    }
    #[cfg(target_os = "android")]
    return super::android::data_dir();
    #[cfg(not(target_os = "android"))]
    Ok(dirs::data_dir()
        .context("Не удалось найти каталог данных пользователя")?
        .join("Xopilot"))
}

static SESSION: std::sync::RwLock<Option<PathBuf>> = std::sync::RwLock::new(None);
pub fn app_data_dir() -> Result<PathBuf> {
    if let Some(path) = SESSION
        .read()
        .map_err(|_| anyhow::anyhow!("Ошибка локальной сессии"))?
        .clone()
    {
        return Ok(path);
    }
    base_data_dir()
}
pub fn set_session(root: Option<PathBuf>) -> Result<()> {
    *SESSION
        .write()
        .map_err(|_| anyhow::anyhow!("Ошибка локальной сессии"))? = root;
    Ok(())
}

pub fn models_dir() -> Result<PathBuf> {
    match std::env::var_os("XOPILOT_MODELS_DIR") {
        Some(path) => Ok(PathBuf::from(path)),
        // Веса общие для устройства; история и материалы каждого аккаунта раздельны.
        None => Ok(base_data_dir()?.join("models")),
    }
}
