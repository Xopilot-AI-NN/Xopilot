// Описание: Настоящая SQLCipher восстанавливает раздел, чат, черновик и положение прокрутки.
use xopilot::services::{
    db::Store,
    drafts::Draft,
    ui_session::{self, Screen, Session},
};

/// Перезапуск процесса не должен превращать открытые настройки в новый пустой чат.
#[test]
fn session_and_draft_survive_reopening_database() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("history.db");
    let key = "e".repeat(64);
    let store = Store::new(
        advanced_xopilot::db::Database::open(&path, &key)
            .unwrap(),
    );
    let chat = store
        .with(|db| Ok(db.create_chat("Продолжение")?))
        .unwrap();
    let session = Session {
        screen: Screen::Settings,
        settings_section: Some(1),
        sidebar: false,
        history: vec![Screen::Chat],
        scrolls: [("Персонализация".into(), 320.0)].into(),
        chat_scroll: -180.0,
    };
    let draft = Draft {
        text: "Неотправленный текст".into(),
        files: vec![],
    };
    ui_session::save(&store, &session, Some(chat), &draft)
        .unwrap();
    drop(store);
    let store = Store::new(
        advanced_xopilot::db::Database::open(&path, &key)
            .unwrap(),
    );
    assert!(ui_session::load(&store).unwrap() == session);
    assert_eq!(
        store
            .with(|db| {
                xopilot::services::drafts::read_draft(
                    db, chat,
                )
            })
            .unwrap(),
        draft
    );
}

/// Повреждённая или устаревшая UI-запись не блокирует открытие защищённой истории.
#[test]
fn obsolete_ui_session_is_bounded_and_optional() {
    let store = Store::new(
        advanced_xopilot::db::Database::open(
            ":memory:",
            &"f".repeat(64),
        )
        .unwrap(),
    );
    store
        .with(|db| {
            db.set_setting(
                "ui_session_v1",
                r#"{"screen":"settings","settings_section":99}"#,
            )?;
            Ok(())
        })
        .unwrap();
    assert_eq!(
        ui_session::load(&store).unwrap().settings_section,
        None
    );
    store
        .with(|db| {
            db.set_setting("ui_session_v1", "not json")?;
            Ok(())
        })
        .unwrap();
    assert_eq!(
        ui_session::load(&store).unwrap().screen,
        Screen::Chat
    );
}
