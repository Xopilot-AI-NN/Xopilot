// Описание: Снимок окна переживает пересоздание процесса; «Назад» не закрывает корневой WebView.
// Обычный возврат из фона сохраняет всю живую Dioxus-модель. SQLCipher нужен для другого случая:
// Android уже уничтожил процесс, и вместо него создан новый. Снимок не является кешем секретов ОС.
use crate::{
    app::state::{self, AppState, Screen},
    services::{self, ui_session::Session},
};
use dioxus::prelude::*;

/// Собирает только навигацию и прокрутку, не сериализуя пароли и незавершённые команды агента.
fn snapshot(value: &AppState) -> Session {
    Session {
        screen: value.screen,
        settings_section: value.settings_section,
        sidebar: value.sidebar,
        history: value.dialog_history.clone(),
        scrolls: value.session_scrolls.clone(),
        chat_scroll: value.chat_scroll,
    }
}

/// Сохраняет снимок и актуальный черновик вне потока интерфейса.
async fn persist(state: Signal<AppState>) {
    let (store, session, active, draft) = {
        let value = state.peek();
        (
            value.store.clone(),
            snapshot(&value),
            value.active,
            value.draft.clone(),
        )
    };
    if let Some(store) = store {
        let result = services::runtime::blocking(move || {
            services::ui_session::save(&store, &session, active, &draft)
        })
        .await;
        state::report(state, result);
    }
}

#[derive(serde::Deserialize)]
struct LifecycleEvent {
    kind: String,
    #[serde(default)]
    scrolls: std::collections::HashMap<String, f64>,
    #[serde(default)]
    chat_scroll: f64,
}

/// Фиксирует навигацию при изменении и немедленно при уходе приложения в фон.
/// Короткий debounce объединяет несколько изменений одного перехода; visibilitychange
/// не ждёт этого таймера и отдельно сохраняет самый свежий черновик перед остановкой UI.
#[component]
pub fn build_session_lifecycle() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let navigation = use_memo(move || {
        let value = state.read();
        (value.ready, snapshot(&value))
    });
    let _writer = use_resource(move || {
        let (ready, _) = navigation.read().clone();
        async move {
            if ready {
                services::runtime::background(async {
                    tokio::time::sleep(std::time::Duration::from_millis(150)).await
                })
                .await;
                persist(state).await;
            }
        }
    });
    use_future(move || async move {
        let mut bridge = document::eval(include_str!("session_lifecycle.js"));
        while let Ok(event) = bridge.recv::<LifecycleEvent>().await {
            {
                let mut value = state.write();
                value.session_scrolls = event.scrolls;
                value.chat_scroll = event.chat_scroll;
            }
            if event.kind == "back" {
                let value = state.peek();
                let approval = value.approval.is_some();
                let pending = value.pending_screen.is_some() || value.pending_section.is_some();
                let root = value.screen == Screen::Chat && !value.sidebar;
                let drawer = value.sidebar;
                drop(value);
                if approval {
                    state::answer_action(state, false);
                } else if pending {
                    state.write().pending_screen = None;
                    state.write().pending_section = None;
                } else if drawer {
                    state.write().sidebar = false;
                } else if !root {
                    state::dismiss(state);
                } else {
                    persist(state).await;
                    #[cfg(target_os = "android")]
                    state::report(state, services::android::move_to_background());
                }
            } else if event.kind == "background" {
                persist(state).await;
            }
        }
    });
    rsx! {}
}
