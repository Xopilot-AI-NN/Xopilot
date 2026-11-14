use crate::{
    app::{
        shared::icons,
        state::{self, AppState},
    },
    services,
};
use dioxus::prelude::*;
use std::sync::{
    Arc,
    atomic::{AtomicBool, Ordering},
};
use tokio_util::sync::CancellationToken;
/// Добавляет распознанную речь в черновик для проверки и редактирования.
#[component]
pub fn build_voice_button() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let mut phase = use_signal(|| 0_u8);
    let mut cancellation =
        use_signal(|| None::<CancellationToken>);
    let disposed =
        use_hook(|| Arc::new(AtomicBool::new(false)));
    let cleanup = disposed.clone();
    use_drop(move || {
        cleanup.store(true, Ordering::Relaxed);
        if let Some(token) = cancellation.read().as_ref() {
            token.cancel();
        }
        if *phase.read() > 0
            && let Ok(mut value) = state.try_write()
        {
            value.uploading = false;
        }
    });
    let label = match *phase.read() {
        1 => "Остановить запись",
        2 => "Отменить распознавание",
        _ => "Диктовка",
    };
    rsx! {
        button {
            class: "brand-button tone-ai",
            style: "--button-size:40px",
            r#type: "button",
            title: label,
            "aria-label": label,
            disabled: state.read().busy || state.read().live_active ||
                    (state.read().uploading && * phase.read() == 0),
            onclick: move |_| {
                if let Some(token) = cancellation.read().as_ref() {
                    token.cancel();
                    return;
                }
                let config = match state::store(state)
                    .and_then(|store| services::generation::audio_configuration(&store))
                {
                    Ok(config) => config,
                    Err(error) => {
                        state::report(state, Err(error));
                        return;
                    }
                };
                let token = CancellationToken::new();
                cancellation.set(Some(token.clone()));
                phase.set(1);
                state.write().uploading = true;
                let chat = state.read().active;
                let disposed = disposed.clone();
                spawn(async move {
                    let result = async {
                        let bytes = services::voice::record(token).await?;
                        if disposed.load(Ordering::Relaxed) {
                            return Ok(());
                        }
                        let token = CancellationToken::new();
                        cancellation.set(Some(token.clone()));
                        phase.set(2);
                        let text = services::runtime::background(
                                services::voice::transcribe(config, bytes, token),
                            )
                            .await?;
                        if disposed.load(Ordering::Relaxed) || state.read().active != chat {
                            return Ok(());
                        }
                        if text.is_empty() {
                            state.write().notice = Some(
                                "Речь не распознана".into(),
                            );
                        } else {
                            let mut value = state.write();
                            if !value.draft.text.is_empty() {
                                value.draft.text.push(' ');
                            }
                            value.draft.text.push_str(&text);
                            drop(value);
                            state::persist_draft(state).await?;
                        }
                        Ok(())
                    }
                        .await;
                    if !disposed.load(Ordering::Relaxed) {
                        phase.set(0);
                        cancellation.set(None);
                        state.write().uploading = false;
                        state::report(state, result);
                    }
                });
            },
            icons::build_icon { name: if *phase.read() == 0 { "mic" } else { "stop" } }
        }
    }
}
