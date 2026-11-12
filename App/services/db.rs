// Файл: App/services/db.rs
// Описание: Единая точка доступа к SQLCipher; блокирующие вызовы идут в worker.
use advanced_xopilot::db::Database;
use anyhow::{Context, Result, anyhow};
use serde::{Serialize, de::DeserializeOwned};
use std::sync::{Arc, Mutex};

#[derive(Clone)]
pub struct Store(Arc<Mutex<Database>>);

impl Store {
    /// Открывает прежнюю SQLCipher с совместимым ключом ОС или Android Keystore.
    pub fn open() -> Result<Self> {
        let root = super::paths::base_data_dir()?;
        super::account_deletion::perform_pending_erasure(
            &root,
        )?;
        let path = root.join("xopilot.db");
        #[cfg(not(target_os = "android"))]
        let db = advanced_xopilot::open_database(&path)
            .map_err(|e| anyhow!(e))?;
        #[cfg(target_os = "android")]
        let db = {
            std::fs::create_dir_all(
                path.parent().unwrap(),
            )?;
            let existing = path
                .metadata()
                .map(|m| m.len() > 0)
                .unwrap_or(false);
            let key =
                super::android::database_key(existing)?;
            Database::open(&path, &key)?
        };
        Ok(Self::new(db))
    }

    /// Создаёт владельца ресурса с исходным состоянием.
    pub fn new(db: Database) -> Self {
        Self(Arc::new(Mutex::new(db)))
    }
    /// Сверяет владельца базы без использования SQL ID, которые повторяются в разных профилях.
    pub fn same_database(&self, other: &Self) -> bool {
        Arc::ptr_eq(&self.0, &other.0)
    }

    /// Сериализует доступ к базе в пределах одной короткой операции.
    pub fn with<T>(
        &self,
        call: impl FnOnce(&Database) -> Result<T>,
    ) -> Result<T> {
        let db = self.0.lock().map_err(|_| {
            anyhow!("Хранилище занято после ошибки")
        })?;
        call(&db)
    }

    /// Переносит блокирующую работу с базой в worker Tokio.
    pub async fn run<T: Send + 'static>(
        &self,
        call: impl FnOnce(&Database) -> Result<T>
        + Send
        + 'static,
    ) -> Result<T> {
        let store = self.clone();
        tokio::task::spawn_blocking(move || {
            store.with(call)
        })
        .await?
    }

    /// Читает сохранённое значение без изменения неизвестных полей.
    pub fn read<T: DeserializeOwned + Default>(
        &self,
        key: &str,
    ) -> Result<T> {
        self.with(|db| read_json(db, key))
    }

    /// Записывает значение через общее хранилище.
    pub fn write<T: Serialize>(
        &self,
        key: &str,
        value: &T,
    ) -> Result<()> {
        self.with(|db| write_json(db, key, value))
    }
}

/// Читает JSON-настройку, используя значение по умолчанию при её отсутствии.
pub fn read_json<T: DeserializeOwned + Default>(
    db: &Database,
    key: &str,
) -> Result<T> {
    match db.get_setting(key)? {
        Some(raw) => serde_json::from_str(&raw)
            .with_context(|| format!("Повреждена настройка {key}; исходные данные сохранены")),
        None => Ok(T::default()),
    }
}

/// Сериализует значение и сохраняет его под прежним ключом настройки.
pub fn write_json<T: Serialize>(
    db: &Database,
    key: &str,
    value: &T,
) -> Result<()> {
    db.set_setting(key, &serde_json::to_string(value)?)?;
    Ok(())
}
