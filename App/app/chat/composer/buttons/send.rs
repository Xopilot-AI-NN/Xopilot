// Описание: Та же иконка отправки; во время ответа — остановка.
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
    rsx! {
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
