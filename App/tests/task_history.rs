// Описание: Карточки шагов переживают перезапуск и не попадают в соседний разговор.
use advanced_xopilot::db::Database;
use serde_json::json;
use xopilot::services::{
    db::Store,
    task_history::{self, Action},
};
/// Результаты принадлежат запросу; незаконченный шаг после запуска помечается прерванным.
#[test]
fn tool_cards_are_scoped_to_message_and_survive_reopening() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("history.db");
    let (first, second, request) = {
        let store = Store::new(Database::open(&path, &"c".repeat(64)).unwrap());
        let ids = store
            .with(|db| {
                let first = db.create_chat("First")?;
                let second = db.create_chat("Second")?;
                let request =
                    db.add_message_full(first, "user", "Read file", None, None, &[], None)?;
                db.add_message_full(second, "user", "Other", None, None, &[], None)?;
                Ok((first, second, request))
            })
            .unwrap();
        task_history::save(
            &store,
            ids.2,
            &[
                Action {
                    id: 1,
                    tool: "read_project_file".into(),
                    arguments: json!({"path":"file.txt"}),
                    state: "completed".into(),
                    output: json!({"ok":true,"result":"hello"}),
                    seconds: 0.5,
                },
                Action {
                    id: 2,
                    state: "running".into(),
                    ..Default::default()
                },
            ],
        )
        .unwrap();
        ids
    };
    let store = Store::new(Database::open(&path, &"c".repeat(64)).unwrap());
    let messages = store.with(|db| Ok(db.get_messages(first)?)).unwrap();
    let history = task_history::load(&store, &messages).unwrap();
    assert_eq!(history[&request][0].output["result"], "hello");
    assert_eq!(history[&request][1].state, "interrupted");
    let other = store.with(|db| Ok(db.get_messages(second)?)).unwrap();
    assert!(task_history::load(&store, &other).unwrap().is_empty());
    store
        .with(|db| {
            db.delete_message(request)?;
            assert!(
                db.get_setting(&format!("agent_actions_v1:{request}"))?
                    .is_none()
            );
            Ok(())
        })
        .unwrap();
}
