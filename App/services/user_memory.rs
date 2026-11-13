// Описание: Категории памяти совместимы с profile_v1 прежнего приложения.
// Записи обновляются под блокировкой SQLCipher. Редактор сверяет прежний текст,
// чтобы параллельное автоизвлечение не перезаписало изменение пользователя.
use super::db::{Store, read_json, write_json};
use anyhow::{Result, ensure};
use serde_json::{Value, json};

/// Возвращает сохранённую память, включая неизвестные поля прежней версии.
pub fn read(store: &Store) -> Result<Value> {
    let profile = super::profile::read(store)?;
    Ok(profile
        .get("memory")
        .filter(|v| v.is_object())
        .cloned()
        .unwrap_or_else(|| json!({"enabled":true,"automatic":true,"items":[]})))
}

/// Изменяет память в одной транзакции с сохранением остальных полей профиля.
fn modify(
    store: &Store,
    operation: impl FnOnce(&mut Value) -> Result<()>,
) -> Result<()> {
    store.with(|db| {
        let mut profile: Value = read_json(db, "profile_v1")?;
        ensure!(profile.is_object(), "Профиль ещё не создан");
        if !profile["memory"].is_object() {
            profile["memory"] = json!({"enabled":true,"automatic":true,"items":[]});
        }
        if profile["memory"].get("items").is_none() {
            profile["memory"]["items"] = json!([]);
        }
        operation(&mut profile["memory"])?;
        write_json(db, "profile_v1", &profile)
    })
}

/// Сохраняет переключатели без изменения существующих записей.
pub fn configure(
    store: &Store,
    enabled: bool,
    automatic: bool,
) -> Result<()> {
    modify(store, |memory| {
        memory["enabled"] = enabled.into();
        memory["automatic"] = automatic.into();
        Ok(())
    })
}

/// Добавляет запись или сохраняет правку только при совпадении исходного текста.
pub fn save(
    store: &Store,
    id: &str,
    original: &str,
    text: &str,
    category: &str,
    automatic: bool,
) -> Result<()> {
    ensure!(
        !text.trim().is_empty()
            && text.chars().count() <= 1000,
        "Введите от 1 до 1000 символов"
    );
    ensure!(
        ["fact", "name", "preferences", "work", "goals"]
            .contains(&category),
        "Неизвестная категория"
    );
    modify(store, |memory| {
        let items = memory["items"]
            .as_array_mut()
            .ok_or_else(|| {
                anyhow::anyhow!("Повреждён список памяти")
            })?;
        if id.is_empty() {
            if items.iter().any(|item| {
                item["text"].as_str() == Some(text.trim())
            }) {
                return Ok(());
            }
            ensure!(
                items.len() < 500,
                "Память заполнена, удалите лишние записи"
            );
            items.push(json!({"id":uuid::Uuid::new_v4().to_string(),"text":text.trim(),"category":category,"automatic":automatic,"updated":super::canvases::now()}));
        } else {
            let item = items
                .iter_mut()
                .find(|item| item["id"] == id)
                .ok_or_else(|| {
                    anyhow::anyhow!("Запись уже удалена")
                })?;
            ensure!(
                item["text"].as_str() == Some(original),
                "Запись изменена в другом окне. Откройте её заново"
            );
            item["text"] = text.trim().into();
            item["category"] = category.into();
            item["updated"] = json!(super::canvases::now());
            item["automatic"] = false.into();
        }
        Ok(())
    })
}

/// Удаляет только выбранную версию записи, сохраняя конкурентные изменения.
pub fn remove(
    store: &Store,
    id: &str,
    original: &str,
) -> Result<()> {
    modify(store, |memory| {
        let items = memory["items"]
            .as_array_mut()
            .ok_or_else(|| {
                anyhow::anyhow!("Повреждён список памяти")
            })?;
        if let Some(index) =
            items.iter().position(|item| item["id"] == id)
        {
            ensure!(
                items[index]["text"].as_str()
                    == Some(original),
                "Запись изменилась. Обновите список"
            );
            items.remove(index);
        }
        Ok(())
    })
}

/// Преобразует явное утверждение в самостоятельный факт без домысливания.
/// Сохраняем исходное значение имени или предпочтения, меняя только точку зрения.
pub(crate) fn statement(
    text: &str,
) -> Option<(&'static str, String)> {
    let mut text =
        text.trim().trim_matches(['"', '«', '»']);
    for prefix in [
        "запомни, что ",
        "запомни: ",
        "запомни, ",
        "запомни ",
        "кстати, ",
        "привет, ",
    ] {
        if text.to_lowercase().starts_with(prefix) {
            text = text.get(prefix.len()..)?.trim();
        }
    }
    let lower = text.to_lowercase();
    for (prefix, category, description) in [
        ("меня зовут ", "name", "Пользователя зовут"),
        ("my name is ", "name", "The user's name is"),
        (
            "я предпочитаю ",
            "preferences",
            "Пользователь предпочитает",
        ),
        ("i prefer ", "preferences", "The user prefers"),
        ("я работаю ", "work", "Пользователь работает"),
        ("моя цель ", "goals", "Цель пользователя —"),
    ] {
        if lower.starts_with(prefix) {
            let value = text
                .get(prefix.len()..)?
                .trim()
                .trim_end_matches(['.', '!']);
            let value = if category == "name" {
                value
                    .split(',')
                    .next()?
                    .split(" и ")
                    .next()?
                    .trim()
                    .trim_matches(['"', '«', '»'])
            } else {
                value
            };
            if value.is_empty()
                || (category == "name"
                    && (value.split_whitespace().count()
                        > 5
                        || value
                            .to_lowercase()
                            .starts_with("не ")
                        || value
                            .to_lowercase()
                            .starts_with("not ")))
            {
                return None;
            }
            return Some((
                category,
                format!("{description} {value}"),
            ));
        }
    }
    None
}

/// Исправляет прежние автоматические цитаты при открытии профиля.
/// Ручные записи и неизвестные поля остаются доступны в прежнем формате.
pub(crate) fn normalize_legacy(profile: &mut Value) {
    if let Some(items) = profile
        .get_mut("memory")
        .and_then(|memory| memory.get_mut("items"))
        .and_then(Value::as_array_mut)
    {
        for item in items {
            if item["automatic"] == true
                && let Some((category, text)) = item["text"]
                    .as_str()
                    .and_then(statement)
            {
                item["text"] = text.into();
                item["category"] = category.into();
            }
        }
    }
}

/// Извлекает короткие явные утверждения, сохраняя каждый факт отдельной записью.
/// Вопросы и сообщения с секретами пропускаем до любых изменений базы.
pub fn capture(store: &Store, text: &str) -> Result<()> {
    let memory = read(store)?;
    if memory["enabled"] == false
        || memory["automatic"] == false
    {
        return Ok(());
    }
    let lower = text.trim().to_lowercase();
    if text.chars().count() > 1000
        || text.contains('?')
        || [
            "парол",
            "password",
            "token",
            "токен",
            "secret",
            "секрет",
            "ключ",
            "sk-",
            "http",
        ]
        .iter()
        .any(|word| lower.contains(word))
    {
        return Ok(());
    }
    let statements = text
        .replace(" и я ", ". Я ")
        .replace(", я ", ". Я ");
    let facts: Vec<_> = statements
        .split(['.', '!', '\n', ';'])
        .filter_map(statement)
        .collect();
    if facts.is_empty() {
        return Ok(());
    }
    modify(store, |memory| {
        // Повторно проверяем переключатели под той же блокировкой, что и запись.
        if memory["enabled"] == false
            || memory["automatic"] == false
        {
            return Ok(());
        }
        let items = memory["items"]
            .as_array_mut()
            .ok_or_else(|| {
                anyhow::anyhow!("Повреждён список памяти")
            })?;
        for (category, text) in facts {
            if items.iter().any(|item| {
                item["text"].as_str() == Some(&text)
            }) {
                continue;
            }
            // Новое явно названное имя заменяет прежнее автоматически извлечённое
            // имя. Пользовательские правки не перезаписываются автоизвлечением.
            if category == "name"
                && let Some(item) =
                    items.iter_mut().find(|item| {
                        item["category"] == "name"
                            && item["automatic"] == true
                    })
            {
                item["text"] = text.into();
                item["updated"] =
                    json!(super::canvases::now());
                continue;
            }
            ensure!(
                items.len() < 500,
                "Память заполнена, удалите лишние записи"
            );
            items.push(json!({"id":uuid::Uuid::new_v4().to_string(),"text":text,"category":category,"automatic":true,"updated":super::canvases::now()}));
        }
        Ok(())
    })
}

/// Выключенная память не попадает в инструкции. Ограничиваем размер контекста.
pub fn context(store: &Store) -> Result<String> {
    let memory = read(store)?;
    if memory["enabled"] == false {
        return Ok(String::new());
    }
    Ok(memory["items"]
        .as_array()
        .into_iter()
        .flatten()
        .take(50)
        .filter_map(|item| item["text"].as_str())
        .map(|text| format!("- {text}\n"))
        .collect::<String>()
        .chars()
        .take(6000)
        .collect())
}
