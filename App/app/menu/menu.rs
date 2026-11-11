// Файл: App/app/menu/menu.rs
// Описание: Rail 76px и выезжающая панель 280px с общей палитрой приложения.
use crate::app::{
    menu::buttons::brand,
    shared::icons,
    state::{self, AppState, Screen},
};
use dioxus::prelude::*;

const TOP: &[(&str, &str, &str, Screen)] = &[
    (
        "workspaces",
        "Рабочие пространства",
        "navigate",
        Screen::Workspaces,
    ),
    ("chat_bubble_outline", "Чаты", "navigate", Screen::Chats),
    (
        "library_books_outlined",
        "Материалы",
        "navigate",
        Screen::Materials,
    ),
    (
        "lock_outlined",
        "Защищённые чаты",
        "navigate",
        Screen::Private,
    ),
];

/// Строит основную панель навигации.
#[component]
pub fn build_menu() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let busy = state.read().busy;
    let open = state.read().sidebar;
    rsx! {
        aside {
            class: if open { "navigation-rail rail-hidden" } else { "navigation-rail" },
            "aria-label": "Главное меню",
            div {
                class: "rail-group",
                brand::build_brand_button {
                    icon: "menu",
                    label: "Открыть меню",
                    size: 50,
                    onclick: move |_| state.write().sidebar = true,
                }
                brand::build_brand_button {
                    icon: "add_comment",
                    label: "Новый чат",
                    role: "create",
                    size: 50,
                    disabled: busy,
                    onclick: move |_| {
                        spawn(async move {
                            let result = state::new_chat(state).await;
                            state::report(state, result);
                        });
                    },
                }
                for &(icon, label, role, screen) in TOP {
                    brand::build_brand_button {
                        icon,
                        label,
                        role,
                        size: 50,
                        onclick: move |_| state::navigate(state, screen),
                    }
                }
            }
            div {
                class: "rail-group",
                brand::build_brand_button {
                    icon: "settings",
                    label: "Настройки",
                    size: 50,
                    onclick: move |_| state::navigate(state, Screen::Settings),
                }
                brand::build_brand_button {
                    icon: "person",
                    label: "Аккаунт",
                    size: 50,
                    onclick: move |_| state::navigate(state, Screen::Account),
                }
            }
        }
    }
}

/// Открывает доступное выдвижное меню на узком экране.
#[component]
pub fn build_menu_overlay() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let mut query = use_signal(String::new);
    let value = state.read();
    let chats = value.chats.clone();
    let active = value.active;
    let open = value.sidebar;
    let busy = value.busy;
    drop(value);
    use_effect(use_reactive((&open,), move |(open,)| {
        if open {
            document::eval(include_str!("../shared/dialog_focus.js"));
        } else {
            document::eval("document.getElementById('chat-prompt')?.focus({preventScroll:true});");
        }
    }));
    let needle = query.read().to_lowercase();
    rsx! {
        // HTML inert — булев атрибут: даже inert="false" блокирует клики.
        // При открытии удаляем атрибут целиком, а не меняем его строковое значение.
        div {
            class: if open { "drawer-layer open" } else { "drawer-layer" },
            inert: if open { None } else { Some("") },
            button {
                class: "drawer-scrim",
                title: "Закрыть меню",
                "aria-label": "Закрыть меню",
                tabindex: -1,
                onclick: move |_| state.write().sidebar = false,
            }
            aside {
                class: "drawer",
                "aria-label": "Навигация и ваши чаты",
                role: if open { Some("dialog") } else { None },
                "aria-modal": if open { Some("true") } else { None },
                tabindex: -1,
                onkeydown: move |event| {
                    if event.key() == Key::Escape {
                        event.stop_propagation();
                        state.write().sidebar = false;
                    }
                },
                nav {
                    class: "drawer-navigation",
                    button {
                        class: "drawer-item",
                        disabled: busy,
                        onclick: move |_| {
                            spawn(async move {
                                let result = state::new_chat(state).await;
                                state::report(state, result);
                            });
                        },
                        span {
                            class: "drawer-badge tone-create",
                            icons::build_icon {
                                name: "add_comment",
                            }
                        }
                        span {
                            "Новый чат"
                        }
                    }
                    for (icon, label, screen) in [
                        ("chat_bubble_outline", "Чаты", Screen::Chats),
                        ("workspaces", "Рабочие пространства", Screen::Workspaces),
                        ("library_books_outlined", "Материалы", Screen::Materials),
                        ("lock_outlined", "Защищённые чаты", Screen::Private),
                    ]
                    {
                        button {
                            class: "drawer-item",
                            onclick: move |_| state::navigate(state, screen),
                            span {
                                class: "drawer-badge tone-navigate",
                                icons::build_icon {
                                    name: icon,
                                }
                            }
                            span {
                                "{label}"
                            }
                        }
                    }
                }
                div {
                    class: "drawer-history",
                    h3 {
                        "Ваши чаты"
                    }
                    label {
                        class: "outlined-search",
                        icons::build_icon {
                            name: "search",
                        }
                        input {
                            placeholder: "Найти чат",
                            "aria-label": "Найти чат",
                            value: "{query}",
                            oninput: move |e| query.set(e.value()),
                        }
                    }
                    div {
                        class: "recent-chats",
                        for chat in chats.into_iter().filter(|chat| chat.title.to_lowercase().contains(&needle)) {
                            button {
                                key: "{chat.id}",
                                class: if active == Some(chat.id) { "recent-chat active" } else { "recent-chat" },
                                disabled: busy,
                                onclick: move |_| {
                                    spawn(async move {
                                        let result = state::switch_chat(state, chat.id).await;
                                        state::report(state, result);
                                    });
                                },
                                icons::build_icon {
                                    name: "chat_bubble_outline",
                                }
                                span {
                                    class: "recent-chat-copy",
                                    strong {
                                        "{chat.title}"
                                    }
                                    small {
                                        "Обычный чат · сообщений: {chat.count}"
                                    }
                                }
                            }
                        }
                    }
                }
                nav {
                    class: "drawer-navigation drawer-bottom",
                    for (icon, label, screen) in [
                        ("settings", "Настройки", Screen::Settings),
                        ("person", "Аккаунт", Screen::Account),
                    ]
                    {
                        button {
                            class: "drawer-item",
                            onclick: move |_| state::navigate(state, screen),
                            span {
                                class: "drawer-badge tone-navigate",
                                icons::build_icon {
                                    name: icon,
                                }
                            }
                            span {
                                "{label}"
                            }
                        }
                    }
                }
            }
        }
    }
}
