// Файл: App/services/paths.rs
// Описание: Доступные для записи каталоги, совместимые с прежней установкой.
#[cfg(not(target_os = "android"))]
use anyhow::Context;
use anyhow::Result;
use std::path::PathBuf;

/// Определяет каталог устройства с учётом тестового переопределения пути.
pub fn base_data_dir() -> Result<PathBuf> {
    if let Some(path) = std::env::var_os("XOPILOT_DATA_DIR")
    {
        return Ok(PathBuf::from(path));
    }
    #[cfg(target_os = "android")]
    {
        static ROOT: std::sync::OnceLock<PathBuf> =
            std::sync::OnceLock::new();
        if let Some(root) = ROOT.get() {
            return Ok(root.clone());
        }
        let root = super::android::data_dir()?;
        let _ = ROOT.set(root.clone());
        return Ok(root);
    }
    #[cfg(not(target_os = "android"))]
    Ok(dirs::data_dir()
        .context(
            "Не удалось найти каталог данных пользователя",
        )?
        .join("Xopilot"))
}

/// Все данные относятся к автоматически созданному профилю устройства.
pub fn app_data_dir() -> Result<PathBuf> {
    base_data_dir()
}

/// Выбирает общий каталог весов вне зашифрованной истории.
pub fn models_dir() -> Result<PathBuf> {
    match std::env::var_os("XOPILOT_MODELS_DIR") {
        Some(path) => Ok(PathBuf::from(path)),
        // Веса общие для устройства; история и материалы каждого аккаунта раздельны.
        None => Ok(base_data_dir()?.join("models")),
    }
}
