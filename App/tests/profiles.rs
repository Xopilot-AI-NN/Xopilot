// Описание: Первый запуск не требует регистрации и сохраняет один постоянный профиль.
use advanced_xopilot::db::Database;
use serde_json::json;
use xopilot::services::{db::Store, profile};
/// Повторное открытие не меняет UUID, имя, память и неизведанные поля профиля.
#[test]
fn automatic_profile_is_stable_and_preserves_existing_data()
{
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("profile.db");
    let id = {
        let store = Store::new(
            Database::open(&path, &"a".repeat(64)).unwrap(),
        );
        store
            .write(
                "profile_v1",
                &json!({"name":"Денис","avatar":"","future_field":7,"memory":{"fact":"Keep"}}),
            )
            .unwrap();
        profile::ensure_local(&store).unwrap();
        let value = profile::read(&store).unwrap();
        assert_eq!(value["name"], "Денис");
        value["id"].as_str().unwrap().to_owned()
    };
    let store = Store::new(
        Database::open(&path, &"a".repeat(64)).unwrap(),
    );
    profile::ensure_local(&store).unwrap();
    let value = profile::read(&store).unwrap();
    assert_eq!(value["id"], id);
    assert_eq!(value["future_field"], 7);
    assert_eq!(value["memory"]["fact"], "Keep");
    assert!(!dir.path().join("accounts").exists());
}
