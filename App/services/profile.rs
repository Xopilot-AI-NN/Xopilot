// Описание: Профиль и память. Не теряем поля, записанные предыдущей версией.
use super::db::{Store, read_json, write_json};
use anyhow::{Result, ensure};
use serde_json::{Value, json};

/// Создаёт постоянный профиль первого запуска, сохраняя прежнее имя, фото и память.
pub fn ensure_local(store: &Store) -> Result<()> {
    store.with(|db| {
        let mut value: Value = read_json(db, "profile_v1")?;
        let original = value.clone();
        if !value.is_object() {
            value = json!({"name": db.get_setting("profile_name")?.unwrap_or_else(|| "Пользователь".into()), "avatar": ""});
        }
        if value["id"].as_str().is_none() { value["id"] = uuid::Uuid::new_v4().to_string().into(); }
        if value.get("created_at").is_none() { value["created_at"] = json!(super::canvases::now()); }
        // Уже созданный профиль не вызывает fsync при каждом возвращении в приложение.
        if value != original { write_json(db, "profile_v1", &value)?; }
        // Один раз заменяем прежний ручной выбор новой автоматической политикой.
        if db.get_setting("compute_policy_v1")?.is_none() {
            db.set_setting("llm_backend", "auto")?;
            db.set_setting("compute_policy_v1", "1")?;
        }
        Ok(())
    })
}

/// Читает сохранённое значение без изменения неизвестных полей.
pub fn read(store: &Store) -> Result<Value> {
    store.with(|db| {
        let value: Value = read_json(db, "profile_v1")?;
        Ok(if value.is_object() { value } else { json!({"name": db.get_setting("profile_name")?.unwrap_or_else(|| "Пользователь".into()), "avatar": ""}) })
    })
}

/// Обновляет существующую запись с сохранением её идентичности.
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
/// Проверяет имя и обновляет его без изменения памяти пользователя.
pub fn rename(store: &Store, name: &str) -> Result<()> {
    ensure!(
        !name.trim().is_empty()
            && name.chars().count() <= 50
            && !name.chars().any(char::is_control),
        "Введите имя от 1 до 50 символов"
    );
    store.with(|db| {
        let mut value: Value = read_json(db, "profile_v1")?;
        if !value.is_object() {
            value = json!({"avatar":""});
        }
        value["name"] = name.trim().into();
        db.set_setting("profile_name", name.trim())?;
        write_json(db, "profile_v1", &value)
    })
}
/// Ограничивает декодирование изображения, обрезает до 256×256 и сохраняет в SQLCipher.
pub fn avatar(store: &Store, bytes: &[u8]) -> Result<String> {
    use base64::Engine as _;
    ensure!(bytes.len() <= 8 * 1024 * 1024, "Изображение больше 8 МиБ");
    let mut reader = image::ImageReader::new(std::io::Cursor::new(bytes)).with_guessed_format()?;
    let mut limits = image::Limits::default();
    limits.max_image_width = Some(8192);
    limits.max_image_height = Some(8192);
    limits.max_alloc = Some(96 * 1024 * 1024);
    reader.limits(limits);
    let picture = reader
        .decode()?
        .resize_to_fill(256, 256, image::imageops::FilterType::Triangle);
    let mut result = std::io::Cursor::new(Vec::new());
    picture.write_to(&mut result, image::ImageFormat::Png)?;
    let encoded = base64::prelude::BASE64_STANDARD.encode(result.into_inner());
    store.with(|db|{let mut value=read_json::<Value>(db,"profile_v1")?;if !value.is_object(){value=json!({"name":db.get_setting("profile_name")?.unwrap_or_else(||"Пользователь".into())});}value["avatar"]=encoded.clone().into();write_json(db,"profile_v1",&value)})?;
    Ok(encoded)
}
/// Читает выбранное изображение с ограничением 8 МиБ и передаёт нормализатору.
pub fn avatar_file(store: &Store, path: &std::path::Path) -> Result<String> {
    use std::io::Read;
    let mut bytes = Vec::new();
    std::fs::File::open(path)?
        .take(8 * 1024 * 1024 + 1)
        .read_to_end(&mut bytes)?;
    avatar(store, &bytes)
}

/// Собирает язык ответа, имя и память пользователя для системного контекста.
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
