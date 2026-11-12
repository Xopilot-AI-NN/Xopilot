// Описание: Каталог и общий фоновый загрузчик; закрытие окна не останавливает скачивание.
use crate::{
    app::{
        shared::icons,
        state::{self, AppState, Screen},
    },
    services::{
        self,
        model_installer::{self, MODELS},
    },
};
use dioxus::prelude::*;

/// Собирает каталог моделей с актуальными фазами загрузок.
#[component]
pub fn build_model_catalog() -> Element {
    let state = use_context::<Signal<AppState>>();
    let mut statuses = use_signal(|| {
        MODELS
            .iter()
            .map(|m| model_installer::progress(m.id))
            .collect::<Vec<_>>()
    });
    use_future(move || async move {
        loop {
            let next = MODELS
                .iter()
                .map(|m| model_installer::progress(m.id))
                .collect::<Vec<_>>();
            if *statuses.peek() != next {
                statuses.set(next);
            }
            services::runtime::background(async {
                tokio::time::sleep(
                    std::time::Duration::from_millis(250),
                )
                .await
            })
            .await;
        }
    });
    rsx! {
        div {
            class: "model-catalog",
            for (index, spec) in MODELS.iter().copied().enumerate() {
                crate::app::models::model_download::build_model_row {
                    key: "{spec.id}",
                    id: spec.id.to_string(),
                    progress: statuses.read().get(index).cloned().unwrap_or_default(),
                }
            }
            super::import::build_model_import {
            }
            button {
                class: "settings-navigation-row model-api-row",
                onclick: move |_| state::navigate(state, Screen::Api),
                span {
                    class: "preference-icon tone-ai",
                    icons::build_icon {
                        name: "api",
                    }
                }
                span {
                    class: "catalog-copy",
                    strong {
                        "Подключить API"
                    }
                    small {
                        "Google AI Studio, OpenRouter или свой сервер"
                    }
                }
                icons::build_icon {
                    name: "chevron_right",
                }
            }
            div {
                class: "model-catalog-footer",
                p {
                    class: "notice",
                    "Файлы хранятся на устройстве. Во время скачивания можно закрыть это окно."
                }
                button {
                    class: "text-button",
                    disabled: state.read().busy,
                    onclick: move |_| {
                        spawn(async move {
                            state::report(
                                state,
                                services::runtime::blocking(services::litert::unload).await,
                            );
                        });
                    },
                    "Освободить память"
                }
            }
            if !services::litert::available() {
                p {
                    class: "notice",
                    "В этой сборке отсутствует библиотека LiteRT. Нужна сборка со встроенным runtime."
                }
            }
        }
    }
}
