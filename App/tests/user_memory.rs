// Описание: Проверяем хранение памяти и конфликтующие правки в настоящей SQLCipher.
use xopilot::services::{context_compaction, db::Store, profile, user_memory};

#[test]
fn memory_capture_respects_settings_and_preserves_concurrent_edits() {
    let store =
        Store::new(advanced_xopilot::db::Database::open(":memory:", &"a".repeat(64)).unwrap());
    profile::ensure_local(&store).unwrap();
    user_memory::capture(&store, "Меня зовут Денис").unwrap();
    user_memory::capture(&store, "Как меня зовут?").unwrap();
    user_memory::capture(&store, "Я предпочитаю пароль secret").unwrap();
    let memory = user_memory::read(&store).unwrap();
    assert_eq!(memory["items"].as_array().unwrap().len(), 1);
    let item = &memory["items"][0];
    let id = item["id"].as_str().unwrap();
    user_memory::save(
        &store,
        id,
        "Меня зовут Денис",
        "Имя исправлено",
        "name",
        false,
    )
    .unwrap();
    assert!(
        user_memory::save(
            &store,
            id,
            "Меня зовут Денис",
            "Устаревшая правка",
            "name",
            false
        )
        .is_err()
    );
    user_memory::configure(&store, false, false).unwrap();
    assert!(user_memory::context(&store).unwrap().is_empty());
    user_memory::capture(&store, "Я предпочитаю Rust").unwrap();
    assert_eq!(
        user_memory::read(&store).unwrap()["items"]
            .as_array()
            .unwrap()
            .len(),
        1
    );
}

#[test]
fn compaction_keeps_latest_request_and_does_not_modify_source_history() {
    let mut messages = vec![serde_json::json!({"role":"system","content":"Инструкции"})];
    for i in 0..50 {
        messages.push(serde_json::json!({"role":"user","content":format!("Запись {i} {}", "история ".repeat(40))}));
    }
    let compacted = context_compaction::compact(messages.clone());
    assert_eq!(compacted.first(), messages.first());
    assert_eq!(compacted.last(), messages.last());
    assert!(compacted.len() < messages.len());
    assert!(
        compacted[1]["content"]
            .as_str()
            .unwrap()
            .contains("earlier_conversation")
    );
    assert_eq!(messages.len(), 51);
}
