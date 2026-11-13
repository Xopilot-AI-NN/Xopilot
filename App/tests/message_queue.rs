// Добавил проверки очереди и сохранения нового черновика во время ответа.
use xopilot::{
    app::state::AppState, services::drafts::Draft,
};

/// Очередь хранит текст и вложения в порядке отправки. Новый ввод остаётся отдельным.
#[test]
fn keeps_next_draft_separate_from_running_request() {
    let mut state = AppState {
        active: Some(1),
        busy: true,
        ..Default::default()
    };
    state.draft = Draft {
        text: "Первое".into(),
        files: vec![(
            "фото.png".into(),
            "/tmp/photo.png".into(),
        )],
    };
    state.enqueue_draft().unwrap();
    state.draft.text = "Второе".into();
    state.enqueue_draft().unwrap();
    state.draft.text = "Ещё печатаю".into();
    assert_eq!(
        state
            .message_queue
            .pop_front()
            .unwrap()
            .files
            .len(),
        1
    );
    assert_eq!(
        state.message_queue.pop_front().unwrap().text,
        "Второе"
    );
    assert_eq!(state.draft.text, "Ещё печатаю");
    assert!(state.busy);
}

/// Переполненная очередь и отсутствие чата не удаляют набранное сообщение.
#[test]
fn rejected_request_keeps_draft() {
    let mut state = AppState::default();
    state.draft.text = "Сохранить текст".into();
    assert!(state.enqueue_draft().is_err());
    assert_eq!(state.draft.text, "Сохранить текст");
    state.active = Some(1);
    for _ in 0..20 {
        state.message_queue.push_back(Draft::default());
    }
    assert!(state.enqueue_draft().is_err());
    assert_eq!(state.draft.text, "Сохранить текст");
    assert_eq!(state.message_queue.len(), 20);
}

/// Пустой Enter не создаёт задачи, но вложение без текста можно отправить.
#[test]
fn accepts_attachment_without_text() {
    let mut state = AppState {
        active: Some(1),
        ..Default::default()
    };
    state.enqueue_draft().unwrap();
    assert!(state.message_queue.is_empty());
    state.draft.files.push((
        "voice.wav".into(),
        "/tmp/voice.wav".into(),
    ));
    state.enqueue_draft().unwrap();
    assert_eq!(state.message_queue.len(), 1);
    assert!(state.draft.files.is_empty());
}
