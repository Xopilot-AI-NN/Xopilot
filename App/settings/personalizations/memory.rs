// Описание: Видимые записи памяти, категории и защита от конкурентного редактирования.
use crate::{
    app::state::{self, AppState},
    services::user_memory,
};
use dioxus::prelude::*;
use serde_json::Value;

/// Показывает сохранённые факты и управляет автоизвлечением из сообщений пользователя.
#[component]
pub fn build_memory() -> Element {
    let state = use_context::<Signal<AppState>>();
    let mut revision = use_signal(|| 0u64);
    let mut data = use_signal(Value::default);
    let mut selected = use_signal(Value::default);
    let mut text = use_signal(String::new);
    let mut category = use_signal(|| "fact".to_string());
    let _load = use_resource(move || {
        let _revision = *revision.read();
        async move {
            match state::store(state)
                .and_then(|store| user_memory::read(&store))
            {
                Ok(value) => data.set(value),
                Err(error) => {
                    state::report(state, Err(error))
                }
            }
        }
    });
    let enabled = data.read()["enabled"] != false;
    let automatic = data.read()["automatic"] != false;
    let items = data.read()["items"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    rsx! {
        h2 {
            class: "section-title",
            "Сохранённые сведения"
        }
        div {
            class: "memory-toggle-grid",

            button {
                r#type: "button",
                class: if enabled {
                    "memory-toggle active"
                } else {
                    "memory-toggle inactive"
                },
                "aria-pressed": enabled.to_string(),

                onclick: move |_| {
                    let result = state::store(state).and_then(|store| {
                        user_memory::configure(
                            &store,
                            !enabled,
                            automatic,
                        )
                    });
                    state::report(state, result);
                    revision += 1;
                },

                span {
                    class: "material-icons",
                    "psychology"
                }
                span {
                    class: "memory-toggle-title",
                    "Использовать память"
                }
            }

            button {
                r#type: "button",
                class: if automatic {
                    "memory-toggle active"
                } else {
                    "memory-toggle inactive"
                },
                "aria-pressed": automatic.to_string(),

                onclick: move |_| {
                    let result = state::store(state).and_then(|store| {
                        user_memory::configure(
                            &store,
                            enabled,
                            !automatic,
                        )
                    });
                    state::report(state, result);
                    revision += 1;
                },

                span {
                    class: "material-icons",
                    "auto_awesome"
                }
                span {
                    class: "memory-toggle-title",
                    "Автозапоминание"
                }
            }
        }
        for item in items {
            section {
                class: "section",
                p {
                    {item["text"].as_str().unwrap_or_default()}
                }
                div {
                    class: "row",
                    button {
                        class: "button",
                        onclick: {
                            let item = item.clone();
                            move |_| {
                                text.set(item["text"].as_str().unwrap_or_default().into());
                                category.set(item["category"].as_str().unwrap_or("fact").into());
                                selected.set(item.clone());
                            }
                        },
                        "Изменить запись"
                    }
                    button {
                        class: "button danger",
                        onclick: move |_| {
                            let result = state::store(state).and_then(|store| user_memory::remove(&store, item["id"].as_str().unwrap_or_default(), item["text"].as_str().unwrap_or_default()));
                            state::report(state, result);
                            revision += 1;
                        },
                        "Удалить запись"
                    }
                }
            }
        }
        label {
            class: "field",
            "Факт или предпочтение"
            input {
                "aria-label": "Запись памяти",
                value: "{text}",
                oninput: move |event| text.set(event.value()),
            }
        }
        crate::app::shared::select::build_select {
            id: "memory-category",
            label: "Категория памяти",
            value: category.read().clone(),
            options: vec![("fact".into(), "Сведения".into()), ("name".into(), "Имя".into()), ("preferences".into(), "Предпочтения".into()), ("work".into(), "Работа".into()), ("goals".into(), "Цели".into())],
            onchange: move |value| category.set(value),
        }
        button {
            class: "button",
            disabled: text.read().trim().is_empty(),
            onclick: move |_| {
                let item = selected.read().clone();
                let result = state::store(state).and_then(|store| user_memory::save(&store, item["id"].as_str().unwrap_or_default(), item["text"].as_str().unwrap_or_default(), &text.read(), &category.read(), false));
                if result.is_ok() {
                    selected.set(Value::Null);
                    text.set(String::new());
                    revision += 1;
                }
                state::report(state, result);
            },
            "Сохранить запись"
        }
    }
}
