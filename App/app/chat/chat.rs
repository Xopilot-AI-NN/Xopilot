// Файл: App/app/chat/chat.rs
// Описание: Заголовок, лента и ввод собраны в общем окне.
use super::{composer, messages::message};
use crate::app::{
    menu::buttons::brand,
    shared::icons,
    state::{self, AppState, Screen},
};
use dioxus::prelude::*;

/// Собирает заголовок, сообщения, карточки действий и строку ввода.
#[component]
pub fn build_chat() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let mut query = use_signal(String::new);
    let mut searching = use_signal(|| false);
    let mut bookmarks_only = use_signal(|| false);
    let mut popup = use_signal(|| false);
    let mut deleting = use_signal(|| false);
    let value = state.read();
    let messages = value.messages.clone();
    let bookmarks = value.bookmarks.clone();
    let actions = value.action_history.clone();
    let active = value.active;
    let title = value
        .chats
        .iter()
        .find(|c| Some(c.id) == active)
        .map(|c| c.title.clone())
        .unwrap_or_else(|| "Новый чат".into());
    let workspace = if value.workspace_name.is_empty() {
        "Все чаты".to_owned()
    } else {
        value.workspace_name.clone()
    };
    let streaming = value.streaming.clone();
    let pending_notes = value.pending_notes.clone();
    let busy = value.busy;
    drop(value);
    use_effect(use_reactive((&active,), move |_| {
        // Фильтр предыдущего чата не должен скрывать сообщения нового.
        query.set(String::new());
        searching.set(false);
        bookmarks_only.set(false);
        popup.set(false);
        deleting.set(false);
    }));
    let needle = query.read().to_lowercase();
    let filtered: Vec<_> = messages
        .iter()
        .rev()
        .filter(|m| {
            m.content.to_lowercase().contains(&needle)
                && (!*bookmarks_only.read()
                    || bookmarks.contains(&m.id))
        })
        .cloned()
        .collect();
    rsx! {
        header {
            class: "chat-header",
            div {
                class: "mobile-header-menu",
                brand::build_brand_button {
                    icon: "menu",
                    label: "Открыть меню",
                    size: 44,
                    onclick: move |_| state.write().sidebar = true,
                }
            }
            div {
                class: "header-title",
                strong {
                    "{title}"
                }
                small {
                    "{workspace}"
                }
            }
            div {
                class: "desktop-header-actions",
                brand::build_brand_button {
                    icon: "add_comment_outlined",
                    label: "Новый чат",
                    size: 36,
                    role: "create",
                    disabled: busy,
                    onclick: move |_| {
                        spawn(async move {
                            let result = state::new_chat(state).await;
                            state::report(state, result);
                        });
                    },
                }
                brand::build_brand_button {
                    icon: "forum_outlined",
                    label: "Все чаты",
                    size: 36,
                    onclick: move |_| state::navigate(state, Screen::Chats),
                }
                button {
                    id: "chat-tools-desktop",
                    class: "plain-icon",
                    title: "Поиск, закладки и экспорт",
                    "aria-label": "Поиск, закладки и экспорт",
                    "aria-expanded": *popup.read(),
                    onclick: move |_| {
                        let open = *popup.read();
                        popup.set(!open);
                    },
                    icons::build_icon {
                        name: "search",
                    }
                }
                brand::build_brand_button {
                    icon: "draw_outlined",
                    label: "Canvas",
                    size: 36,
                    role: "ai",
                    onclick: move |_| state::navigate(state, Screen::Canvas),
                }
                brand::build_brand_button {
                    icon: "delete_outline",
                    label: "Удалить чат",
                    size: 36,
                    role: "danger",
                    disabled: busy,
                    onclick: move |_| deleting.set(true),
                }
            }
            div {
                class: "mobile-header-actions",
                div {
                    id: "chat-tools-mobile",
                    brand::build_brand_button {
                        icon: "more_horiz",
                        label: "Действия чата",
                        size: 44,
                        onclick: move |_| {
                            let open = *popup.read();
                            popup.set(!open);
                        },
                    }
                }
            }
            if *popup.read() {
                crate::app::shared::popover::build_popover {
                    id: "chat-tools-menu",
                    anchor: "chat-tools-desktop",
                    onclose: move |_| popup.set(false),
                    button {
                        class: "popup-item mobile-popup-item",
                        onclick: move |_| {
                            popup.set(false);
                            spawn(async move {
                                let result = state::new_chat(state).await;
                                state::report(state, result);
                            });
                        },
                        icons::build_icon {
                            name: "add_comment",
                        }
                        "Новый чат"
                    }
                    for (icon, label, screen) in [
                        ("forum", "Все чаты", Screen::Chats),
                        ("draw", "Canvas", Screen::Canvas),
                        ("library_books", "Материалы", Screen::Materials),
                    ]
                    {
                        button {
                            class: "popup-item mobile-popup-item",
                            onclick: move |_| {
                                popup.set(false);
                                state::navigate(state, screen);
                            },
                            icons::build_icon {
                                name: icon,
                            }
                            "{label}"
                        }
                    }
                    button {
                        class: "popup-item",
                        onclick: move |_| {
                            popup.set(false);
                            bookmarks_only.set(false);
                            searching.set(true);
                        },
                        icons::build_icon {
                            name: "search",
                        }
                        "Поиск в чате"
                    }
                    button {
                        class: "popup-item",
                        onclick: move |_| {
                            popup.set(false);
                            state::navigate(state, Screen::Templates);
                        },
                        icons::build_icon {
                            name: "text_snippet",
                        }
                        "Шаблоны запросов"
                    }
                    button {
                        class: "popup-item",
                        onclick: move |_| {
                            popup.set(false);
                            bookmarks_only.set(true);
                            query.set(String::new());
                            searching.set(true);
                        },
                        icons::build_icon {
                            name: "bookmark_border",
                        }
                        "Закладки"
                    }
                    button {
                        class: "popup-item",
                        onclick: move |_| {
                            popup.set(false);
                            document::eval(
                                "const list=document.getElementById('chat-messages');if(list)list.scrollTop=0;",
                            );
                        },
                        icons::build_icon {
                            name: "arrow_downward",
                        }
                        "К последним сообщениям"
                    }
                    button {
                        class: "popup-item",
                        onclick: move |_| {
                            popup.set(false);
                            spawn(async move {
                                let result = state::export_chat(state).await;
                                state::report(state, result);
                            });
                        },
                        icons::build_icon {
                            name: "download",
                        }
                        "Экспортировать чат"
                    }
                }
            }
        }
        if *searching.read() {
            div {
                class: "message-search",
                label {
                    class: "outlined-search",
                    icons::build_icon {
                        name: "search",
                    }
                    input {
                        "aria-label": "Поиск по сообщениям",
                        placeholder: if *bookmarks_only.read() { "Поиск в закладках" } else { "Поиск в чате" },
                        value: "{query}",
                        oninput: move |e| query.set(e.value()),
                    }
                }
                button {
                    class: "plain-icon",
                    title: "Закрыть поиск",
                    onclick: move |_| {
                        query.set(String::new());
                        searching.set(false);
                        bookmarks_only.set(false);
                    },
                    icons::build_icon {
                        name: "close",
                    }
                }
            }
        }
        div {
            class: "chat-body",
            if *searching.read() && filtered.is_empty() && !busy {
                div {
                    class: "empty search-empty",
                    role: "status",
                    icons::build_icon {
                        name: "search",
                    }
                    h2 {
                        if *bookmarks_only.read() && needle.is_empty() {
                            "Закладок пока нет"
                        } else {
                            "Ничего не найдено"
                        }
                    }
                    p {
                        if *bookmarks_only.read() {
                            "Добавьте сообщение в закладки через его меню."
                        } else {
                            "Попробуйте другой запрос."
                        }
                    }
                }
            } else if messages.is_empty() && !busy {
                div {
                    class: "empty",
                    icons::build_icon {
                        name: "auto_awesome",
                    }
                    h1 {
                        "С чего начнём?"
                    }
                    p {
                        "Напишите вопрос, прикрепите файл или начните голосовой разговор."
                    }
                }
            } else {
                section {
                    class: "messages",
                    id: "chat-messages",
                    "aria-label": "Сообщения",
                    for (index,note) in pending_notes.iter().enumerate() {
                        article {
                            key: "pending-note-{index}",
                            class: "message user pending-note",
                            div {class:"message-bubble", "{note}"}
                            small {class:"notice", "Уточнение · ожидает безопасного шага"}
                        }
                    }
                    if busy {
                        crate::app::shared::components::reply_activity::build_reply_activity {
                            text: streaming,
                        }
                    }
                    for item in filtered {
                        div {
                            key: "{item.id}",
                            class: "message-turn",
                            message::build_message {
                                message: item.clone(),
                            }
                            if let Some(actions) = actions.get(&item.id) {
                                crate::app::tasks::action_card::build_action_cards {
                                    actions: actions.clone(),
                                }
                            }
                        }
                    }
                }
            }
        }
        composer::prompt::build_prompt {
        }
        if *deleting.read() {
            div {
                class: "modal-backdrop confirmation-backdrop",
                section {
                    class: "confirmation",
                    role: "alertdialog",
                    "aria-label": "Удалить чат?",
                    "aria-modal": "true",
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
                            onclick: move |_| deleting.set(false),
                            "Отмена"
                        }
                        button {
                            class: "button danger",
                            onclick: move |_| {
                                spawn(async move {
                                    if let Some(id) = active {
                                        let result = state::delete_chat(state, id).await;
                                        state::report(state, result);
                                    }
                                    deleting.set(false);
                                });
                            },
                            "Удалить"
                        }
                    }
                }
            }
        }
    }
}
