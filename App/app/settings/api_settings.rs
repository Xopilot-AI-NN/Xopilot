// Файл: App/app/settings/api_settings.rs
// Описание: Gemini, OpenRouter и любой совместимый сервер, в том числе локальный.
use crate::{
    app::state::{self, AppState},
    services::{
        self,
        api_chat::{self, ApiConfig},
    },
};
use dioxus::prelude::*;

/// Редактирует провайдера API, адрес, модель и защищённый ключ.
#[component]
pub fn build_api_settings() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let mut url = use_signal(String::new);
    let mut model = use_signal(String::new);
    let mut key = use_signal(String::new);
    let mut loaded = use_signal(|| false);
    let mut status = use_signal(String::new);
    let mut dirty = use_signal(|| false);
    crate::app::shared::unsaved::use_unsaved(dirty);
    use_future(move || async move {
        let result = async {
            let store = state::store(state)?;
            let config =
                services::runtime::blocking(move || {
                    api_chat::configuration(&store)
                })
                .await?;
            url.set(config.url);
            model.set(config.model);
            key.set(config.key);
            loaded.set(true);
            Ok(())
        }
        .await;
        loaded.set(true);
        state::report(state, result);
    });
    let busy = state.read().busy;
    rsx! {
        section {
            class: "section",
            h2 {
                "Модель и API"
            }
            p {
                class: "notice",
                "Запросы идут напрямую выбранному провайдеру. API-ключ хранится в зашифрованной локальной базе."
            }
            div {
                class: "row",
                for (label, endpoint) in [
                    ("Google AI Studio", "https://generativelanguage.googleapis.com/v1beta/openai"),
                    ("OpenRouter", "https://openrouter.ai/api/v1"),
                    ("llama-server", "http://127.0.0.1:8080/v1"),
                    ("Ollama", "http://127.0.0.1:11434/v1"),
                ]
                {
                    button {
                        class: "button",
                        disabled: busy,
                        onclick: move |_| {
                            // Смена провайдера не переносит ему ключ от прежнего подключения.
                            if *url.peek() != endpoint {
                                key.set(String::new());
                            }
                            url.set(endpoint.into());
                            dirty.set(true);
                        },
                        "{label}"
                    }
                }
            }
            label {
                class: "field",
                "Адрес API"
                input {
                    value: "{url}",
                    placeholder: "https://example.com/v1",
                    disabled: busy,
                    oninput: move |e| {
                        let next = e.value();
                        if next != *url.peek() {
                            key.set(String::new());
                        }
                        url.set(next);
                        dirty.set(true);
                    },
                }
            }
            label {
                class: "field",
                "Идентификатор модели"
                input {
                    value: "{model}",
                    placeholder: "Идентификатор из каталога провайдера",
                    disabled: busy,
                    oninput: move |e| {
                        model.set(e.value());
                        dirty.set(true);
                    },
                }
            }
            label {
                class: "field",
                "API-ключ"
                input {
                    r#type: "password",
                    autocomplete: "off",
                    value: "{key}",
                    disabled: busy,
                    oninput: move |e| {
                        key.set(e.value());
                        dirty.set(true);
                    },
                }
            }
            button {
                class: "button primary",
                disabled: busy || !*loaded.read(),
                onclick: move |_| {
                    spawn(async move {
                        let result = async {
                            let store = state::store(state)?;
                            let config = ApiConfig {
                                url: url.read().clone(),
                                model: model.read().clone(),
                                key: key.read().clone(),
                            };
                            let selected = config.model.clone();
                            services::runtime::blocking(move || api_chat::save_configuration(
                                    &store,
                                    &config,
                                ))
                                .await?;
                            state.write().model = selected;
                            state.write().model_local = false;
                            dirty.set(false);
                            status.set("Настройки модели сохранены".into());
                            Ok(())
                        }
                            .await;
                        state::report(state, result);
                    });
                },
                "Сохранить модель"
            }
            p {
                class: "notice",
                role: "status",
                "{status}"
            }
            p {
                class: "notice",
                "Для встроенной Gemma выберите локальную модель в каталоге. llama-server и Ollama запускаются отдельно."
            }
        }
    }
}
