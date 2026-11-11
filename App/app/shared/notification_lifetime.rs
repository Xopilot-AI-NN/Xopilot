// Описание: Завершённые уведомления живут три секунды независимо от открытого окна.
use crate::{app::state::AppState, services};
use dioxus::prelude::*;
use std::{
    collections::HashMap,
    time::{Duration, Instant},
};

const LIFETIME: Duration = Duration::from_secs(3);

/// Снимает только то сообщение, для которого начался таймер; новое не исчезает раньше срока.
fn use_text_timeout(mut state: Signal<AppState>, error: bool) {
    let current = use_memo(move || {
        if error {
            state.read().error.clone()
        } else {
            state.read().notice.clone()
        }
    });
    let _timer = use_resource(move || {
        let message = current.read().clone();
        async move {
            if message.is_none() {
                return;
            }
            services::runtime::background(async { tokio::time::sleep(LIFETIME).await }).await;
            let mut value = state.write();
            let field = if error {
                &mut value.error
            } else {
                &mut value.notice
            };
            if *field == message {
                *field = None;
            }
        }
    });
}

/// Оставляет активные загрузки и подтверждения, скрывая сообщения и завершённые операции.
#[component]
pub fn build_notification_lifetime() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    use_text_timeout(state, false);
    use_text_timeout(state, true);
    let completed = use_memo(move || state.read().task_completion.clone());
    let _completion_timer = use_resource(move || {
        let message = completed.read().clone();
        async move {
            if message.is_none() {
                return;
            }
            services::runtime::background(async { tokio::time::sleep(LIFETIME).await }).await;
            if state.peek().task_completion == message {
                state.write().task_completion = None;
            }
        }
    });
    use_future(move || async move {
        let mut terminal = HashMap::<String, (String, Instant)>::new();
        loop {
            let import = services::model_import::progress();
            if matches!(import.phase.as_str(), "installed" | "error") {
                let signature = format!("{}:{}:{}", import.phase, import.total, import.message);
                if expired(&mut terminal, "import", signature) {
                    services::model_import::dismiss();
                }
            } else {
                terminal.remove("import");
            }
            for model in services::model_installer::MODELS {
                let progress = services::model_installer::progress(model.id);
                if matches!(progress.phase.as_str(), "installed" | "error") {
                    let signature = format!(
                        "{}:{}:{}",
                        progress.phase, progress.downloaded, progress.error
                    );
                    if expired(&mut terminal, model.id, signature)
                        && !state.peek().dismissed_downloads.contains(model.id)
                    {
                        state.write().dismissed_downloads.insert(model.id.into());
                    }
                } else {
                    terminal.remove(model.id);
                }
            }
            services::runtime::background(async {
                tokio::time::sleep(Duration::from_millis(100)).await
            })
            .await;
        }
    });
    rsx! {}
}

/// Запоминает первый момент завершения; изменение результата запускает новый срок.
fn expired(timers: &mut HashMap<String, (String, Instant)>, id: &str, signature: String) -> bool {
    let entry = timers
        .entry(id.into())
        .or_insert_with(|| (signature.clone(), Instant::now()));
    if entry.0 != signature {
        *entry = (signature, Instant::now());
    }
    entry.1.elapsed() >= LIFETIME
}
