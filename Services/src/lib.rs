// Файл: Services/src/lib.rs
// Разработчик: DenBroLiik
// Описание: Нативное хранилище. Интерфейс обращается к Rust напрямую.

pub mod db;
pub mod security;

use db::Database;
use std::path::Path;

/// Сохраняем путь, ключи и SQLCipher-схему прежней версии.
/// Если ключ потерян, не подменяем существующую историю пустой базой.
pub fn open_database(path: &Path) -> Result<Database, String> {
    let parent = path
        .parent()
        .ok_or("У базы данных нет родительской папки")?;
    std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    let existing = path.metadata().map(|m| m.len() > 0).unwrap_or(false);
    let keys = security::get_db_keys(parent, existing)?;
    let mut last_error = String::from("Ключ истории недоступен");
    for key in keys {
        match Database::open(path, &key) {
            Ok(db) => return Ok(db),
            Err(error) => last_error = error.to_string(),
        }
    }
    Err(last_error)
}
