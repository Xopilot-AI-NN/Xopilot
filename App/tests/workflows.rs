// Описание: Объявления модулей tests в общей структуре приложения.
use advanced_xopilot::db::Database;
use serde_json::json;
use xopilot::services::{
    api_chat,
    canvases::{self, Document},
    chat_store,
    db::Store,
    drafts::{self, Draft},
    profile, prompt_templates,
    workspaces::{self, Workspace},
};

/// Создаёт или получает хранилище данных текущего контекста.
fn store() -> Store {
    Store::new(
        Database::open(":memory:", &"a".repeat(64))
            .unwrap(),
    )
}

/// Проверяет восстановление нужного чата и его черновика.
#[test]
fn chat_and_draft_keep_their_identity_after_reloading() {
    let store = store();
    let first = store
        .with(|db| chat_store::load(db, None))
        .unwrap();
    let draft = Draft {
        text: "Несохранённая идея".into(),
        files: vec![(
            "note.md".into(),
            "/tmp/note.md".into(),
        )],
    };
    let second = store
        .with(|db| {
            drafts::write_draft(db, first.active, &draft)?;
            Ok(db.create_chat("Другой чат")?)
        })
        .unwrap();
    assert_ne!(
        store
            .with(|db| chat_store::load(db, Some(second)))
            .unwrap()
            .active,
        first.active
    );
    let restored = store
        .with(|db| chat_store::load(db, Some(first.active)))
        .unwrap();
    assert_eq!(restored.draft, draft);
}

/// Проверяет сохранность неизвестных полей профиля, Canvas и проекта.
#[test]
fn migration_preserves_unported_profile_canvas_and_workspace_fields()
 {
    let store = store();
    store
        .write(
            "profile_v1",
            &json!({"name":"Денис", "avatar":"", "memory":{"rules":["бережно"]}, "future":true}),
        )
        .unwrap();
    profile::update(&store, "Денис", "Новые инструкции")
        .unwrap();
    let profile = profile::read(&store).unwrap();
    assert_eq!(profile["memory"]["rules"][0], "бережно");
    assert_eq!(profile["future"], true);
    let original = json!([{"id":"old", "title":"Рисунок", "kind":"drawing", "strokes":[{"points":[[0.1,0.2]],"color":"#fff"}], "created_at":12}]);
    store.write(canvases::KEY, &original).unwrap();
    let mut document =
        canvases::list_documents(&store).unwrap().remove(0);
    document.title = "Название".into();
    canvases::save_document(&store, document).unwrap();
    let after: serde_json::Value =
        store.read(canvases::KEY).unwrap();
    assert_eq!(after[0]["strokes"], original[0]["strokes"]);
    assert_eq!(after[0]["created_at"], 12);
    store.write(workspaces::KEY, &json!({"items":[{"id":"w","name":"Проект", "sync_pending_chat_uuids":["uuid"]}],"chats":{},"selected":"all"})).unwrap();
    let mut workspace = workspaces::list_workspaces(&store)
        .unwrap()
        .items
        .remove(0);
    workspace.name = "Новое имя".into();
    workspaces::save_workspace(&store, workspace).unwrap();
    let after: serde_json::Value =
        store.read(workspaces::KEY).unwrap();
    assert_eq!(
        after["items"][0]["sync_pending_chat_uuids"][0],
        "uuid"
    );
}

/// Проверяет, что удаление проекта не удаляет переписку.
#[test]
fn deleting_a_workspace_keeps_its_chats() {
    let store = store();
    let chat = store
        .with(|db| Ok(db.create_chat("Чат")?))
        .unwrap();
    workspaces::save_workspace(
        &store,
        Workspace {
            id: "w".into(),
            name: "Проект".into(),
            ..Default::default()
        },
    )
    .unwrap();
    workspaces::assign_chat(&store, chat, "w").unwrap();
    workspaces::delete_workspace(&store, "w").unwrap();
    assert_eq!(
        store
            .with(chat_store::list_chat_items)
            .unwrap()
            .len(),
        1
    );
    assert!(
        workspaces::list_workspaces(&store)
            .unwrap()
            .chats
            .is_empty()
    );
}

/// Проверяет сохранение шаблонов и документов через SQLCipher.
#[test]
fn templates_and_canvas_survive_the_real_store() {
    let store = store();
    prompt_templates::save(&store, "Ревью", "Проверь код")
        .unwrap();
    let template = prompt_templates::list_templates(&store)
        .unwrap()
        .remove(0);
    assert_eq!(template.body, "Проверь код");
    prompt_templates::delete(&store, &template.id).unwrap();
    assert!(
        prompt_templates::list_templates(&store)
            .unwrap()
            .is_empty()
    );
    let saved = canvases::save_document(
        &store,
        Document {
            title: "Заметка".into(),
            kind: "text".into(),
            content: "# Привет".into(),
            ..Default::default()
        },
    )
    .unwrap();
    assert!(!saved.id.is_empty());
    assert_eq!(
        canvases::list_documents(&store).unwrap()[0]
            .content,
        "# Привет"
    );
}

/// Читает полный HTTP-запрос локального тестового сервера.
async fn read_request(
    stream: &mut tokio::net::TcpStream,
) -> serde_json::Value {
    use tokio::io::AsyncReadExt;
    let mut bytes = Vec::new();
    let header_end;
    loop {
        bytes.push(stream.read_u8().await.unwrap());
        if bytes.ends_with(b"\r\n\r\n") {
            header_end = bytes.len();
            break;
        }
    }
    let headers = String::from_utf8_lossy(&bytes);
    let length: usize = headers
        .lines()
        .find_map(|line| {
            let (key, value) = line.split_once(':')?;
            key.eq_ignore_ascii_case("content-length")
                .then(|| value.trim().parse().unwrap())
        })
        .unwrap();
    bytes.resize(header_end + length, 0);
    stream
        .read_exact(&mut bytes[header_end..])
        .await
        .unwrap();
    serde_json::from_slice(&bytes[header_end..]).unwrap()
}

/// Проверяет потоковые фрагменты и фактически отправленную модель API.
#[tokio::test]
async fn real_http_stream_emits_deltas_and_sends_configured_model()
 {
    use tokio::io::AsyncWriteExt;
    let listener =
        tokio::net::TcpListener::bind("127.0.0.1:0")
            .await
            .unwrap();
    let address = listener.local_addr().unwrap();
    let server = tokio::spawn(async move {
        let (mut stream, _) =
            listener.accept().await.unwrap();
        let body = read_request(&mut stream).await;
        assert_eq!(body["model"], "test-model");
        assert_eq!(
            body["messages"][0]["content"],
            "Привет"
        );
        let response = "data: {\"choices\":[{\"delta\":{\"content\":\"Работает\"}}]}\n\ndata: [DONE]\n\n";
        let header = format!(
            "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {}\r\n\r\n",
            response.len()
        );
        stream.write_all(header.as_bytes()).await.unwrap();
        for part in response.as_bytes().chunks(3) {
            stream.write_all(part).await.unwrap();
            tokio::task::yield_now().await;
        }
    });
    let (tx, mut rx) =
        tokio::sync::mpsc::unbounded_channel();
    let config = api_chat::ApiConfig {
        url: format!("http://{address}/v1"),
        model: "test-model".into(),
        key: String::new(),
    };
    let reply = api_chat::generate_reply(
        config,
        vec![json!({"role":"user", "content":"Привет"})],
        Default::default(),
        tx,
    )
    .await
    .unwrap();
    assert_eq!(reply, "Работает");
    assert_eq!(rx.recv().await.unwrap(), "Работает");
    server.await.unwrap();
}

/// Проверяет отмену ожидания сетевых заголовков.
#[tokio::test]
async fn cancellation_interrupts_waiting_response_headers()
{
    let listener =
        tokio::net::TcpListener::bind("127.0.0.1:0")
            .await
            .unwrap();
    let address = listener.local_addr().unwrap();
    let (accepted, ready) = tokio::sync::oneshot::channel();
    let server = tokio::spawn(async move {
        let (mut stream, _) =
            listener.accept().await.unwrap();
        read_request(&mut stream).await;
        accepted.send(()).unwrap();
        tokio::time::sleep(std::time::Duration::from_secs(
            30,
        ))
        .await;
    });
    let token = tokio_util::sync::CancellationToken::new();
    let request_token = token.clone();
    let (tx, _) = tokio::sync::mpsc::unbounded_channel();
    let request = tokio::spawn(async move {
        api_chat::generate_reply(
            api_chat::ApiConfig {
                url: format!("http://{address}/v1"),
                model: "m".into(),
                key: String::new(),
            },
            vec![],
            request_token,
            tx,
        )
        .await
    });
    ready.await.unwrap();
    token.cancel();
    assert!(
        tokio::time::timeout(
            std::time::Duration::from_secs(1),
            request
        )
        .await
        .unwrap()
        .unwrap()
        .is_err()
    );
    server.abort();
}

/// Запрещает неявную отправку локального чата сохранённому внешнему API.
#[test]
fn migration_never_sends_a_local_chat_to_a_saved_remote_api_implicitly()
 {
    let store = store();
    store
        .write(
            api_chat::KEY,
            &api_chat::ApiConfig {
                url: "https://example.com/v1".into(),
                model: "remote".into(),
                key: "saved-secret".into(),
            },
        )
        .unwrap();
    store
        .with(|db| {
            db.set_setting("chat_provider", "local")?;
            Ok(())
        })
        .unwrap();
    assert!(
        api_chat::selected_configuration(&store).is_err()
    );
    let config = api_chat::configuration(&store).unwrap();
    api_chat::save_configuration(&store, &config).unwrap();
    assert_eq!(
        api_chat::selected_configuration(&store)
            .unwrap()
            .model,
        "remote"
    );
}

thread_local! {
    static UI_STORE: std::cell::RefCell<Option<Store>> = const { std::cell::RefCell::new(None) };
    static UI_STATE: std::cell::RefCell<Option<dioxus::prelude::Signal<xopilot::app::state::AppState>>> = const { std::cell::RefCell::new(None) };
}

/// Собирает тестовое состояние отправки сообщения.
fn action_fixture() -> dioxus::prelude::Element {
    use dioxus::prelude::*;
    let _state = use_context_provider(|| {
        let store = UI_STORE.with(|cell| {
            cell.borrow().as_ref().unwrap().clone()
        });
        let snapshot = store
            .with(|db| chat_store::load(db, None))
            .unwrap();
        let mut value = xopilot::app::state::AppState {
            store: Some(store),
            ready: true,
            ..Default::default()
        };
        value.apply(snapshot);
        value.draft.text = "Тестовый вопрос".into();
        let state = Signal::new(value);
        UI_STATE
            .with(|cell| *cell.borrow_mut() = Some(state));
        state
    });
    rsx! {
        div {

        }
    }
}

/// Проверяет сохранение вопроса и ответа, времени и очистку черновика.
#[tokio::test(flavor = "current_thread")]
async fn send_action_saves_real_user_and_assistant_messages_and_clears_draft()
 {
    use dioxus::prelude::*;
    use tokio::io::AsyncWriteExt;
    let listener =
        tokio::net::TcpListener::bind("127.0.0.1:0")
            .await
            .unwrap();
    let address = listener.local_addr().unwrap();
    let server = tokio::spawn(async move {
        let (mut stream, _) =
            listener.accept().await.unwrap();
        let body = read_request(&mut stream).await;
        assert_eq!(
            body["messages"][1]["content"],
            "Тестовый вопрос"
        );
        let response = "data: {\"choices\":[{\"delta\":{\"content\":\"Тестовый ответ\"}}]}\n\ndata: [DONE]\n\n";
        stream.write_all(format!("HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {}\r\n\r\n{response}", response.len()).as_bytes()).await.unwrap();
    });
    let store = store();
    api_chat::save_configuration(
        &store,
        &api_chat::ApiConfig {
            url: format!("http://{address}/v1"),
            model: "test".into(),
            key: String::new(),
        },
    )
    .unwrap();
    UI_STORE.with(|cell| {
        *cell.borrow_mut() = Some(store.clone())
    });
    let mut dom = VirtualDom::new(action_fixture);
    dom.rebuild_in_place();
    let state =
        UI_STATE.with(|cell| cell.borrow().unwrap());
    let active = state.read().active;
    xopilot::app::state::refresh(state, active)
        .await
        .unwrap();
    assert_eq!(
        state.read().draft.text,
        "Тестовый вопрос",
        "Обновление UI не должно затирать черновик"
    );
    tokio::time::timeout(
        std::time::Duration::from_secs(5),
        xopilot::app::state::send(state),
    )
    .await
    .unwrap()
    .unwrap();
    assert!(!state.read().busy);
    assert!(state.read().draft.text.is_empty());
    assert!(state.read().streaming.is_empty());
    let id = state.read().active.unwrap();
    let messages =
        store.with(|db| Ok(db.get_messages(id)?)).unwrap();
    assert_eq!(messages.len(), 2);
    assert_eq!(messages[0].role, "user");
    assert_eq!(messages[1].role, "ai");
    assert_eq!(messages[1].content, "Тестовый ответ");
    assert!(messages[1].elapsed_seconds.unwrap() >= 0.0);
    assert!(
        store
            .with(|db| drafts::read_draft(db, id))
            .unwrap()
            .text
            .is_empty()
    );
    server.await.unwrap();
    UI_STATE.with(|cell| *cell.borrow_mut() = None);
    UI_STORE.with(|cell| *cell.borrow_mut() = None);
}

/// Проверяет возврат из вложенного окна без потери черновика.
#[test]
fn nested_dialogs_return_to_the_same_settings_section_and_keep_draft()
 {
    use dioxus::prelude::*;
    use xopilot::app::state::{self, Screen};
    UI_STORE
        .with(|cell| *cell.borrow_mut() = Some(store()));
    let mut dom = VirtualDom::new(action_fixture);
    dom.rebuild_in_place();
    let mut state =
        UI_STATE.with(|cell| cell.borrow().unwrap());
    state::navigate(state, Screen::Settings);
    state.write().settings_section = Some(1);
    state::navigate(state, Screen::Model);
    state::navigate(state, Screen::Api);
    state::dismiss(state);
    assert!(state.read().screen == Screen::Model);
    state::dismiss(state);
    assert!(state.read().screen == Screen::Settings);
    assert_eq!(state.read().settings_section, Some(1));
    state::dismiss(state);
    assert!(state.read().screen == Screen::Chat);
    assert!(state.read().dialog_history.is_empty());
    state::navigate(state, Screen::Settings);
    assert_eq!(state.read().settings_section, None);
    assert_eq!(state.read().draft.text, "Тестовый вопрос");
    UI_STATE.with(|cell| *cell.borrow_mut() = None);
    UI_STORE.with(|cell| *cell.borrow_mut() = None);
}

/// Проверяет защиту изменённой формы при переходе назад.
#[test]
fn unsaved_settings_require_a_decision_before_returning_to_the_list()
 {
    use dioxus::prelude::*;
    use xopilot::app::state::{self, Screen};
    UI_STORE
        .with(|cell| *cell.borrow_mut() = Some(store()));
    let mut dom = VirtualDom::new(action_fixture);
    dom.rebuild_in_place();
    let mut state =
        UI_STATE.with(|cell| cell.borrow().unwrap());
    state::navigate(state, Screen::Settings);
    state::select_settings_section(state, Some(0));
    state.write().unsaved = true;
    state::select_settings_section(state, None);
    assert_eq!(state.read().settings_section, Some(0));
    assert_eq!(state.read().pending_section, Some(None));
    state::discard_pending(state);
    assert_eq!(state.read().settings_section, None);
    assert!(!state.read().unsaved);
    UI_STATE.with(|cell| *cell.borrow_mut() = None);
    UI_STORE.with(|cell| *cell.borrow_mut() = None);
}

/// Проверяет совместимость ID закладок и их привязку к чату.
#[test]
fn bookmarks_keep_legacy_identifiers_and_are_scoped_to_their_chat()
 {
    use xopilot::services::message_navigation;
    let store = store();
    let (first, second, message) = store
        .with(|db| {
            let first = db.create_chat("Первый")?;
            let second = db.create_chat("Второй")?;
            let message = db.add_message_full(
                first,
                "user",
                "Закладка",
                None,
                None,
                &[],
                None,
            )?;
            Ok((first, second, message))
        })
        .unwrap();
    assert!(
        message_navigation::toggle(&store, first, message)
            .unwrap()
    );
    let saved: serde_json::Value =
        store.read(message_navigation::KEY).unwrap();
    assert_eq!(
        saved[message.to_string()]["chat_id"],
        first
    );
    assert!(
        message_navigation::marked(&store, first)
            .unwrap()
            .contains(&message)
    );
    assert!(
        message_navigation::marked(&store, second)
            .unwrap()
            .is_empty()
    );
    assert!(
        message_navigation::toggle(&store, second, message)
            .is_err()
    );
    assert!(
        !message_navigation::toggle(&store, first, message)
            .unwrap()
    );
}

/// Проверяет изменение имени и аватара без потери инструкций и памяти.
#[test]
fn profile_avatar_and_name_preserve_memory_and_unknown_fields()
 {
    use base64::Engine as _;
    let store = store();
    store
        .write(
            "profile_v1",
            &json!({"name":"Old","memory":{"fact":"Keep"},"future_field":42}),
        )
        .unwrap();
    store
        .with(|db| {
            db.set_setting(
                "personal_instructions",
                "Keep instructions",
            )?;
            Ok(())
        })
        .unwrap();
    let image = image::DynamicImage::new_rgb8(640, 320);
    let mut file = std::io::Cursor::new(Vec::new());
    image
        .write_to(&mut file, image::ImageFormat::Png)
        .unwrap();
    let avatar =
        profile::avatar(&store, &file.into_inner())
            .unwrap();
    let decoded = base64::prelude::BASE64_STANDARD
        .decode(avatar)
        .unwrap();
    let image = image::load_from_memory(&decoded).unwrap();
    assert_eq!((image.width(), image.height()), (256, 256));
    profile::rename(&store, "New name").unwrap();
    let saved = profile::read(&store).unwrap();
    assert_eq!(saved["name"], "New name");
    assert_eq!(saved["memory"]["fact"], "Keep");
    assert_eq!(saved["future_field"], 42);
    assert!(
        profile::instructions(&store)
            .unwrap()
            .contains("Keep instructions")
    );
    assert!(
        profile::avatar(&store, b"not a picture").is_err()
    );
    assert!(profile::rename(&store, " ").is_err());
}

/// Создание нового чата переносит весь черновик и сохраняет его после повторного открытия.
#[tokio::test(flavor = "current_thread")]
async fn new_chat_keeps_text_and_attachments_in_composer() {
    use dioxus::prelude::*;
    let store = store();
    UI_STORE.with(|cell| {
        *cell.borrow_mut() = Some(store.clone())
    });
    let mut dom = VirtualDom::new(action_fixture);
    dom.rebuild_in_place();
    let mut state =
        UI_STATE.with(|cell| cell.borrow().unwrap());
    state.write().draft.files.push((
        "photo.png".into(),
        "/test/photo.png".into(),
    ));
    let previous = state.read().active.unwrap();
    let draft = state.read().draft.clone();
    xopilot::app::state::new_chat(state).await.unwrap();
    let current = state.read().active.unwrap();
    assert_ne!(previous, current);
    assert_eq!(state.read().draft, draft);
    assert_eq!(
        store
            .with(|db| drafts::read_draft(db, current))
            .unwrap(),
        draft
    );
    assert_eq!(
        store
            .with(|db| drafts::read_draft(db, previous))
            .unwrap(),
        draft
    );
}
