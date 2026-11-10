// Описание: Профиль и память. Не теряем поля, записанные предыдущей версией.
use super::db::{Store, read_json, write_json};
use anyhow::{Result, ensure};
use serde_json::{Value, json};

pub fn read(store: &Store) -> Result<Value> {
    store.with(|db| {
        let value: Value = read_json(db, "profile_v1")?;
        Ok(if value.is_object() { value } else { json!({"name": db.get_setting("profile_name")?.unwrap_or_else(|| "Пользователь".into()), "avatar": ""}) })
    })
}

pub fn update(store: &Store, name: &str, memory: &str) -> Result<()> {
    ensure!(
        !name.trim().is_empty()
            && name.chars().count() <= 50
            && !name.chars().any(char::is_control),
        "Введите имя от 1 до 50 символов"
    );
    store.with(|db| {
        let mut value: Value = read_json(db, "profile_v1")?;
        if !value.is_object() {
            value = json!({"avatar": ""});
        }
        value["name"] = name.trim().into();
        // Отдельный ключ для свободных инструкций не перезаписывает структурированную память.
        db.set_setting("personal_instructions", memory)?;
        db.set_setting("profile_name", name.trim())?;
        write_json(db, "profile_v1", &value)
    })
}

pub fn instructions(store: &Store) -> Result<String> {
    let profile = read(store)?;
    store.with(|db| {
        let personal = db.get_setting("personal_instructions")?.unwrap_or_default();
        let language = if db.get_setting("response_language")?.as_deref() == Some("en") {
            "Reply in English."
        } else {
            "Отвечай по-русски."
        };
        Ok(format!(
            "{language}\nИмя пользователя: {}.\n{}\nСохранённая память пользователя:\n{}",
            profile["name"].as_str().unwrap_or("Пользователь"),
            personal,
            profile
                .get("memory")
                .filter(|v| !v.is_null())
                .map(Value::to_string)
                .unwrap_or_default()
        ))
    })
}
