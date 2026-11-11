// Описание: Проверяем изоляцию настоящих SQLCipher и атомарную смену пароля.
use xopilot::services::local_accounts;
#[test]
fn local_accounts_keep_histories_separate_and_rekey_without_losing_data() {
    let directory = tempfile::tempdir().unwrap();
    // Единственный тест в отдельном test-процессе; другие тесты не видят эту переменную.
    unsafe {
        std::env::set_var("XOPILOT_DATA_DIR", directory.path());
    }
    let first = local_accounts::register("first", "Первый", "first password 123").unwrap();
    let first_id = first.account.as_ref().unwrap().id.clone();
    let old_file = first.root.as_ref().unwrap().join("xopilot.db");
    first
        .store
        .with(|db| {
            let chat = db.create_chat("Личная история первого")?;
            db.add_message_full(
                chat,
                "user",
                "Секретная строка первого",
                None,
                None,
                &[],
                None,
            )?;
            Ok(())
        })
        .unwrap();
    assert!(
        local_accounts::login(&first_id, "first password 123").is_err(),
        "Аккаунт нельзя открыть в двух окнах"
    );
    let second = local_accounts::register("second", "Второй", "second password 123").unwrap();
    let second_id = second.account.as_ref().unwrap().id.clone();
    assert!(
        second
            .store
            .with(|db| Ok(db.list_chats()?))
            .unwrap()
            .is_empty()
    );
    let encrypted = std::fs::read(&old_file).unwrap();
    assert!(
        !encrypted
            .windows(b"SQLite format".len())
            .any(|w| w == b"SQLite format")
    );
    let replacement = local_accounts::change_password(
        &first.store,
        &first_id,
        "first password 123",
        "new password 456",
    )
    .unwrap();
    assert!(
        !old_file.exists(),
        "Старая копия не должна оставаться с прежним паролем"
    );
    drop(first);
    drop(replacement);
    let error = local_accounts::login(&first_id, "first password 123")
        .err()
        .unwrap()
        .to_string();
    assert!(error.contains("Неверный пароль"));
    let restored = local_accounts::login(&first_id, "new password 456").unwrap();
    assert_eq!(
        restored
            .store
            .with(|db| Ok(db.get_messages(db.list_chats()?[0].0)?[0].content.clone()))
            .unwrap(),
        "Секретная строка первого"
    );
    assert!(local_accounts::delete(&restored.store, &first_id, "incorrect password").is_err());
    local_accounts::delete(&restored.store, &first_id, "new password 456").unwrap();
    assert_eq!(local_accounts::list().unwrap().len(), 1);
    assert_eq!(local_accounts::list().unwrap()[0].id, second_id);
    assert!(second.root.as_ref().unwrap().join("xopilot.db").exists());
}
