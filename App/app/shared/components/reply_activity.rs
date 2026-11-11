// Описание: Потоковый ответ и состояние ожидания используют один элемент ленты.
use crate::app::chat::messages::message::markdown_html;
use dioxus::prelude::*;

#[component]
pub fn build_reply_activity(text: String) -> Element {
    rsx! {
        article { class: "message assistant", "aria-live": "polite",
            div { class: "message-bubble",
                if text.is_empty() { span { class: "busy notice", "Готовлю ответ…" } }
                else { div { class: "markdown", dangerous_inner_html: markdown_html(&text) } }
            }
        }
    }
}
