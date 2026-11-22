// Описание: Личные шаблоны; вставка в черновик без автоматической отправки.
use super::db::{Store, read_json, write_json};
use anyhow::{Result, ensure};
use serde::{Deserialize, Serialize};

pub const KEY: &str = "prompt_templates_v1";

#[derive(
    Clone, Debug, PartialEq, Serialize, Deserialize,
)]
pub struct Template {
    pub id: String,
    pub title: String,
    pub body: String,
    pub updated: f64,
}

/// Восстанавливает список пользовательских шаблонов.
pub fn list_templates(
    store: &Store,
) -> Result<Vec<Template>> {
    store.read(KEY)
}

/// Проверяет и сохраняет новую запись в хранилище.
pub fn save(
    store: &Store,
    title: &str,
    body: &str,
) -> Result<()> {
    ensure!(
        !title.trim().is_empty()
            && title.chars().count() <= 80,
        "Введите название до 80 символов"
    );
    ensure!(
        !body.trim().is_empty()
            && body.chars().count() <= 20_000,
        "Введите текст до 20 000 символов"
    );
    store.with(|db| {
        let mut items: Vec<Template> = read_json(db, KEY)?;
        items.push(Template {
            id: uuid::Uuid::new_v4().to_string(),
            title: title.trim().into(),
            body: body.into(),
            updated: super::canvases::now(),
        });
        write_json(db, KEY, &items)
    })
}

/// Удаляет только выбранную запись, сохраняя остальные данные.
pub fn delete(store: &Store, id: &str) -> Result<()> {
    store.with(|db| {
        let mut items: Vec<Template> = read_json(db, KEY)?;
        items.retain(|t| t.id != id);
        write_json(db, KEY, &items)
    })
}

/// Обновляет существующую запись с сохранением её идентичности.
pub fn update(
    store: &Store,
    id: &str,
    title: &str,
    body: &str,
) -> Result<()> {
    ensure!(
        !title.trim().is_empty()
            && title.chars().count() <= 80,
        "Введите название до 80 символов"
    );
    ensure!(
        !body.trim().is_empty()
            && body.chars().count() <= 20_000,
        "Введите текст до 20 000 символов"
    );
    store.with(|db| {
        let mut items: Vec<Template> = read_json(db, KEY)?;
        let item = items
            .iter_mut()
            .find(|item| item.id == id)
            .ok_or_else(|| {
                anyhow::anyhow!("Шаблон уже удалён")
            })?;
        item.title = title.trim().into();
        item.body = body.into();
        item.updated = super::canvases::now();
        write_json(db, KEY, &items)
    })
}
