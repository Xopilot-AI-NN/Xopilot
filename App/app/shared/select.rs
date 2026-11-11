// Описание: Тематический список вместо системного select с чужой палитрой.
use super::{icons, popover};
use dioxus::prelude::*;
#[component]
pub fn build_select(
    id: String,
    label: String,
    value: String,
    options: Vec<(String, String)>,
    onchange: EventHandler<String>,
    #[props(default)] disabled: bool,
) -> Element {
    let mut open = use_signal(|| false);
    let title = options
        .iter()
        .find(|(key, _)| key == &value)
        .map(|(_, name)| name.clone())
        .unwrap_or_default();
    let menu = format!("{id}-options");
    rsx! {
        button {
            id: id.clone(),
            class: "preference-select choice-trigger",
            r#type: "button",
            role: "combobox",
            "aria-label": label,
            "aria-expanded": *open.read(),
            "aria-controls": menu.clone(),
            "aria-haspopup": "listbox",
            disabled,
            onclick: move |_| {
                let next = !*open.peek();
                open.set(next);
            },
            onkeydown: move |e| {
                if matches!(e.key(), Key::ArrowDown | Key::ArrowUp) {
                    e.prevent_default();
                    open.set(true);
                }
            },
            span { "{title}" }
            icons::build_icon { name: "expand_more" }
        }
        if *open.read() {
            popover::build_popover {
                id: menu.clone(),
                anchor: id.clone(),
                role: "listbox",
                onclose: move |_| open.set(false),
                for (key, title) in options {
                    button {
                        class: "popup-item select-option",
                        role: "option",
                        "aria-selected": key == value,
                        onclick: move |_| {
                            onchange.call(key.clone());
                            open.set(false);
                        },
                        span { "{title}" }
                        if key == value {
                            icons::build_icon { name: "check" }
                        }
                    }
                }
            }
        }
    }
}
