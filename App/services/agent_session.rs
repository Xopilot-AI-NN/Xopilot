// Описание: Между запросами сохраняется расширенный разговор инструментов, а не только финальный текст.
use super::{db::Store, generation::Configuration};
use serde_json::{Value, json};
use std::sync::{Mutex, OnceLock};
struct Session {
    store: Store,
    chat: i64,
    config: Configuration,
    logical: Vec<Value>,
    expanded: Vec<Value>,
}
static SESSION: OnceLock<Mutex<Option<Session>>> = OnceLock::new();
/// Добавляет новый вопрос к прежним результатам инструментов, когда чат и история совпадают.
pub fn continue_history(
    store: &Store,
    chat: i64,
    config: &Configuration,
    logical: &[Value],
) -> Vec<Value> {
    let Ok(session) = SESSION.get_or_init(Default::default).lock() else {
        return logical.to_vec();
    };
    if let Some(saved) = session.as_ref()
        && saved.chat == chat
        && saved.store.same_database(store)
        && saved.config == *config
        && super::litert::can_extend(&saved.logical, logical)
    {
        // При подходе к лимиту пересобираем KV из краткой истории, но сохраняем загруженные веса.
        let near_limit = matches!(config, Configuration::Local { .. })
            && super::litert::context_stats().is_ok_and(|stats| stats.tokens > 3000);
        if !near_limit {
            let mut expanded = saved.expanded.clone();
            expanded.extend_from_slice(&logical[saved.logical.len()..]);
            return expanded;
        }
    }
    logical.to_vec()
}
/// Сохраняет точный сырой ответ для KV-кеша и чистый текст для сверки с SQLCipher.
pub fn remember(
    store: &Store,
    chat: i64,
    config: &Configuration,
    logical: &[Value],
    expanded: &[Value],
    answer: &str,
    raw: &str,
) {
    let mut logical = logical.to_vec();
    logical.push(json!({"role":"assistant","content":answer}));
    let mut expanded = expanded.to_vec();
    expanded.push(json!({"role":"assistant","content":raw}));
    if let Ok(mut slot) = SESSION.get_or_init(Default::default).lock() {
        *slot = Some(Session {
            store: store.clone(),
            chat,
            config: config.clone(),
            logical,
            expanded,
        });
    }
}
