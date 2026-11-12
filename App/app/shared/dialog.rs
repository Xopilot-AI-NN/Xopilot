// Описание: Настройки и инструменты открываются поверх чата, с возвратом и защитой несохранённых форм.
use crate::app::{
    shared::icons,
    state::{self, AppState},
};
use dioxus::prelude::*;

/// Собирает общее окно с заголовком, возвратом и прокруткой содержимого.
#[component]
pub fn build_dialog(
    title: String,
    #[props(default = "general".into())] variant: String,
    #[props(default)] settings: bool,
    #[props(default)] narrow: bool,
    #[props(default = true)] immediate: bool,
    #[props(default)] back: Option<
        EventHandler<MouseEvent>,
    >,
    children: Element,
) -> Element {
    let state = use_context::<Signal<AppState>>();
    use_effect(use_reactive((&title,), move |_| {
        document::eval(include_str!("dialog_scroll.js"));
        document::eval(include_str!("dialog_focus.js"));
    }));
    use_drop(move || {
        document::eval(
            "document.getElementById('chat-prompt')?.focus({preventScroll:true});",
        );
    });
    rsx! {
        div {
            class: "modal-backdrop",
            onclick: move |_| state::dismiss(state),
            section {
                class: format!(
                    "dialog dialog-{variant} {}",
                    if settings { "settings-dialog" } else if narrow { "narrow-dialog" } else { "" },
                ),
                role: "dialog",
                "aria-modal": "true",
                "aria-labelledby": "dialog-title",
                tabindex: -1,
                onclick: move |event| event.stop_propagation(),
                onkeydown: move |event| {
                    if event.key() == Key::Escape {
                        event.stop_propagation();
                        state::dismiss(state);
                    }
                },
                header {
                    class: "dialog-header",
                    div {
                        class: "dialog-title-row",
                        if let Some(back) = back {
                            button {
                                class: "plain-icon",
                                title: "Назад к настройкам",
                                onclick: move |event| back.call(event),
                                icons::build_icon {
                                    name: "arrow_back",
                                }
                            }
                        }
                        div {
                            class: "dialog-heading",
                            if settings {
                                span {
                                    class: "dialog-eyebrow",
                                    "Xopilot"
                                }
                            }
                            h1 {
                                id: "dialog-title",
                                "{title}"
                            }
                        }
                        button {
                            class: "plain-icon dialog-close",
                            title: "Закрыть окно",
                            "aria-label": "Закрыть окно",
                            onclick: move |_| state::dismiss(state),
                            icons::build_icon {
                                name: "close",
                            }
                        }
                    }
                    if settings {
                        p {
                            class: "dialog-status",
                            if immediate {
                                "Изменения применяются сразу"
                            } else {
                                "Сохраните изменения перед закрытием"
                            }
                        }
                    }
                }
                div {
                    key: "{title}",
                    class: "dialog-body",
                    "data-scroll-page": title.clone(),
                    {children}
                }
            }
        }
    }
}
