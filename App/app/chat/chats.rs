// Файл: App/app/chat/chats.rs
// Описание: Диалог списка чатов с поиском, переименованием и удалением.
use crate::{
    app::{
        shared::icons,
        state::{self, AppState},
    },
    services,
};
use dioxus::prelude::*;

/// Показывает историю с поиском и действиями над разговорами.
#[component]
pub fn build_chats_dialog() -> Element {
    let state = use_context::<Signal<AppState>>();
    let mut query = use_signal(String::new);
    let mut deleting = use_signal(|| None::<i64>);
    let mut renaming = use_signal(|| None::<i64>);
    let mut title = use_signal(String::new);
    let items = state.read().chats.clone();
    let active = state.read().active;
    let needle = query.read().to_lowercase();
    rsx! {
        div {
            class: "dialog-toolbar",
            label {
                class: "outlined-search",
                icons::build_icon {
                    name: "search",
                }
                input {
                    placeholder: "Поиск по чатам",
                    "aria-label": "Поиск по чатам",
                    value: "{query}",
                    oninput: move |e| query.set(e.value()),
                }
            }
            button {
                class: "button",
                disabled: state.read().busy,
                onclick: move |_| {
                    spawn(async move {
                        let result = state::new_chat(state).await;
                        state::report(state, result);
                    });
                },
                icons::build_icon {
                    name: "add",
                }
                "Новый чат"
            }
        }
        div {
            class: "chat-list",
            for item in items.into_iter().filter(|item| item.title.to_lowercase().contains(&needle)) {
                div {
                    class: if active == Some(item.id) { "chat-list-row active" } else { "chat-list-row" },
                    key: "{item.id}",
                    button {
                        class: "chat-list-link",
                        disabled: state.read().busy,
                        onclick: move |_| {
                            spawn(async move {
                                let result = state::switch_chat(state, item.id).await;
                                state::report(state, result);
                            });
                        },
                        span {
                            class: "chat-avatar",
                            icons::build_icon {
                                name: "chat_bubble_outline",
                            }
                        }
                        span {
                            class: "catalog-copy",
                            strong {
                                "{item.title}"
                            }
                            small {
                                "Обычный чат · сообщений: {item.count}"
                            }
                        }
                    }
                    button {
                        class: "plain-icon",
                        title: "Переименовать чат",
                        disabled: state.read().busy,
                        onclick: move |_| {
                            renaming.set(Some(item.id));
                            title.set(item.title.clone());
                        },
                        icons::build_icon {
                            name: "edit",
                        }
                    }
                    button {
                        class: "plain-icon danger",
                        title: "Удалить чат",
                        disabled: state.read().busy,
                        onclick: move |_| deleting.set(Some(item.id)),
                        icons::build_icon {
                            name: "delete_outline",
                        }
                    }
                }
            }
        }
        if let Some(id) = *renaming.read() {
            section {
                class: "section",
                label {
                    class: "field",
                    "Название чата"
                    input {
                        value: "{title}",
                        oninput: move |e| title.set(e.value()),
                    }
                }
                div {
                    class: "row dialog-actions",
                    button {
                        class: "button",
                        onclick: move |_| renaming.set(None),
                        "Отмена"
                    }
                    button {
                        class: "button primary",
                        onclick: move |_| {
                            spawn(async move {
                                let result = async {
                                    let value = title.read().trim().to_owned();
                                    anyhow::ensure!(
                                        ! value.is_empty(), "Введите название чата"
                                    );
                                    let store = state::store(state)?;
                                    services::runtime::blocking(move || {
                                            store
                                                .with(|db| {
                                                    db.rename_chat(id, &value)?;
                                                    Ok(())
                                                })
                                        })
                                        .await?;
                                    state::refresh(state, active).await?;
                                    renaming.set(None);
                                    Ok(())
                                }
                                    .await;
                                state::report(state, result);
                            });
                        },
                        "Сохранить"
                    }
                }
            }
        }
        if let Some(id) = *deleting.read() {
            section {
                class: "section",
                role: "alert",
                h2 {
                    "Удалить чат?"
                }
                p {
                    "Чат и его сообщения будут удалены. Остальные чаты сохранятся."
                }
                div {
                    class: "row dialog-actions",
                    button {
                        class: "button",
                        onclick: move |_| deleting.set(None),
                        "Отмена"
                    }
                    button {
                        class: "button danger",
                        onclick: move |_| {
                            spawn(async move {
                                let result = state::delete_chat(state, id).await;
                                deleting.set(None);
                                state::report(state, result);
                            });
                        },
                        "Удалить"
                    }
                }
            }
        }
    }
}
