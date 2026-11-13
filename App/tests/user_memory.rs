// Описание: Проверяем хранение памяти и конфликтующие правки в настоящей SQLCipher.
use xopilot::services::{
    context_compaction, db::Store, profile, user_memory,
};

#[test]
fn memory_capture_respects_settings_and_preserves_concurrent_edits()
 {
    let store = Store::new(
        advanced_xopilot::db::Database::open(
            ":memory:",
            &"a".repeat(64),
        )
        .unwrap(),
    );
    profile::ensure_local(&store).unwrap();
    user_memory::capture(&store, "Меня зовут Денис")
        .unwrap();
    user_memory::capture(&store, "Как меня зовут?")
        .unwrap();
    user_memory::capture(
        &store,
        "Я предпочитаю пароль secret",
    )
    .unwrap();
    let memory = user_memory::read(&store).unwrap();
    assert_eq!(
        memory["items"].as_array().unwrap().len(),
        1
    );
    let item = &memory["items"][0];
    let id = item["id"].as_str().unwrap();
    user_memory::save(
        &store,
        id,
        "Пользователя зовут Денис",
        "Имя исправлено",
        "name",
        false,
    )
    .unwrap();
    assert!(
        user_memory::save(
            &store,
            id,
            "Пользователя зовут Денис",
            "Устаревшая правка",
            "name",
            false
        )
        .is_err()
    );
    user_memory::configure(&store, false, false).unwrap();
    assert!(
        user_memory::context(&store).unwrap().is_empty()
    );
    user_memory::capture(&store, "Я предпочитаю Rust")
        .unwrap();
    assert_eq!(
        user_memory::read(&store).unwrap()["items"]
            .as_array()
            .unwrap()
            .len(),
        1
    );
}

#[test]
fn compaction_keeps_latest_request_and_does_not_modify_source_history()
 {
    let mut messages = vec![
        serde_json::json!({"role":"system","content":"Инструкции"}),
    ];
    for i in 0..50 {
        messages.push(serde_json::json!({"role":"user","content":format!("Запись {i} {}", "история ".repeat(40))}));
    }
    let compacted =
        context_compaction::compact(messages.clone());
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

#[test]
fn automatic_memory_stores_separate_facts_and_updates_name()
{
    let store = Store::new(
        advanced_xopilot::db::Database::open(
            ":memory:",
            &"a".repeat(64),
        )
        .unwrap(),
    );
    profile::ensure_local(&store).unwrap();
    user_memory::capture(
        &store,
        "Меня зовут Денис, я предпочитаю Rust!",
    )
    .unwrap();
    let saved = user_memory::read(&store).unwrap();
    assert_eq!(
        saved["items"][0]["text"],
        "Пользователя зовут Денис"
    );
    assert_eq!(
        saved["items"][1]["text"],
        "Пользователь предпочитает Rust"
    );
    user_memory::capture(
        &store,
        "Запомни, меня зовут Денис",
    )
    .unwrap();
    assert_eq!(
        user_memory::read(&store).unwrap()["items"]
            .as_array()
            .unwrap()
            .len(),
        2
    );
    user_memory::capture(
        &store,
        "Меня зовут Денис Александрович",
    )
    .unwrap();
    let changed = user_memory::read(&store).unwrap();
    assert_eq!(
        changed["items"][0]["id"],
        saved["items"][0]["id"]
    );
    assert_eq!(
        changed["items"][0]["text"],
        "Пользователя зовут Денис Александрович"
    );
    assert_eq!(
        changed["items"].as_array().unwrap().len(),
        2
    );
}

#[test]
fn legacy_automatic_quotes_are_normalized_without_rewriting_manual_memory()
 {
    let store = Store::new(
        advanced_xopilot::db::Database::open(
            ":memory:",
            &"a".repeat(64),
        )
        .unwrap(),
    );
    store.write("profile_v1", &serde_json::json!({"name":"Денис","future":42,"memory":{"items":[
        {"id":"automatic","text":"Меня зовут Денис","automatic":true,"category":"name","extra":"keep"},
        {"id":"manual","text":"Я предпочитаю свой текст","automatic":false,"category":"preferences"}
    ]}})).unwrap();
    profile::ensure_local(&store).unwrap();
    let saved = profile::read(&store).unwrap();
    assert_eq!(
        saved["memory"]["items"][0]["text"],
        "Пользователя зовут Денис"
    );
    assert_eq!(
        saved["memory"]["items"][0]["extra"],
        "keep"
    );
    assert_eq!(
        saved["memory"]["items"][1]["text"],
        "Я предпочитаю свой текст"
    );
    assert_eq!(saved["future"], 42);
}
