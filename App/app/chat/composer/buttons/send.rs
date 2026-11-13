// Добавил отдельную отправку в очередь, остановка текущего ответа остаётся рядом.
use crate::app::{
    menu::buttons::brand,
    state::{self, AppState},
};
use dioxus::prelude::*;
/// Переключает отправку и отмену текущего ответа.
#[component]
pub fn build_send_button() -> Element {
    let state = use_context::<Signal<AppState>>();
    let busy = state.read().busy;
    let has_draft =
        !state.read().draft.text.trim().is_empty()
            || !state.read().draft.files.is_empty();
    rsx! {
        if busy && has_draft {
            brand::build_brand_button {
                icon: "playlist_add",
                label: "Отправить после завершения задачи",
                role: "create",
                onclick: move |_| {
                    spawn(async move {
                        let result = state::send(state).await;
                        state::report(state, result);
                    });
                },
            }
        }
        brand::build_brand_button {
            icon: if busy { "stop" } else { "send_rounded" },
            label: if busy { "Остановить ответ" } else { "Отправить сообщение" },
            role: if busy { "danger" } else { "create" },
            onclick: move |_| {
                if busy {
                    state::cancel(state);
                } else {
                    spawn(async move {
                        let result = state::send(state).await;
                        state::report(state, result);
                    });
                }
            },
        }
    }
}
