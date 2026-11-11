// Проверки совместимости SQLCipher при переходе с нативного расширения на библиотеку.
use advanced_xopilot::db::Database;

/// Проверяет повторное открытие зашифрованной истории со связанными полями.
#[test]
fn encrypted_history_reopens_with_attachments_quotes_and_duration() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("xopilot.db");
    let key = "a".repeat(64);
    let chat;
    {
        let db = Database::open(&path, &key).unwrap();
        chat = db.create_chat("История").unwrap();
        db.set_setting("api_config_v1", r#"{"model":"test","key":"secret"}"#)
            .unwrap();
        db.add_message_full(
            chat,
            "user",
            "Привет",
            Some("цитата"),
            Some("ответ"),
            &[("image.png".into(), "/image.png".into())],
            Some(1.25),
        )
        .unwrap();
    }
    let raw = std::fs::read(&path).unwrap();
    assert!(!raw.starts_with(b"SQLite format 3"));
    assert!(Database::open(&path, &"b".repeat(64)).is_err());
    let db = Database::open(&path, &key).unwrap();
    let messages = db.get_messages(chat).unwrap();
    assert_eq!(messages.len(), 1);
    assert_eq!(messages[0].content, "Привет");
    assert_eq!(messages[0].quote.as_deref(), Some("цитата"));
    assert_eq!(messages[0].reply_to.as_deref(), Some("ответ"));
    assert_eq!(messages[0].attachments[0].0, "image.png");
    assert_eq!(messages[0].elapsed_seconds, Some(1.25));
    assert!(
        db.get_setting("api_config_v1")
            .unwrap()
            .unwrap()
            .contains("secret")
    );
}

/// Проверяет каскадное удаление сообщений и вложений вместе с чатом.
#[test]
fn deleting_chat_cascades_messages_and_attachments() {
    let db = Database::open(":memory:", &"a".repeat(64)).unwrap();
    let chat = db.create_chat("chat").unwrap();
    db.add_message_full(
        chat,
        "user",
        "hello",
        None,
        None,
        &[("a".into(), "b".into())],
        None,
    )
    .unwrap();
    assert!(db.delete_chat(chat).unwrap());
    assert!(db.get_messages(chat).unwrap().is_empty());
    assert_eq!(db.total_message_count().unwrap(), 0);
}

/// Проверяет сохранность более новой схемы и неизвестных настроек.
#[test]
fn newer_schema_and_unknown_settings_are_not_downgraded() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("xopilot.db");
    let key = "a".repeat(64);
    {
        let db = Database::open(&path, &key).unwrap();
        db.set_setting("cloud_sync_ledger:account", "preserve")
            .unwrap();
    }
    {
        let conn = rusqlite::Connection::open(&path).unwrap();
        conn.pragma_update(None, "key", &key).unwrap();
        conn.pragma_update(None, "user_version", 99).unwrap();
    }
    let db = Database::open(&path, &key).unwrap();
    assert_eq!(db.schema_version().unwrap(), 99);
    assert_eq!(
        db.get_setting("cloud_sync_ledger:account")
            .unwrap()
            .as_deref(),
        Some("preserve")
    );
}
