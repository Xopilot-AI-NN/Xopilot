// Файл: App/app/chat/messages/message.rs
// Описание: Markdown очищается перед отображением; HTML модели не исполняется.
use crate::app::shared::icons;
use crate::{
    app::state::{self, AppState},
    services,
};
use advanced_xopilot::db::StoredMessage;
use dioxus::prelude::*;

pub fn markdown_html(text: &str) -> String {
    let mut html = String::new();
    pulldown_cmark::html::push_html(
        &mut html,
        pulldown_cmark::Parser::new_ext(
            text,
            pulldown_cmark::Options::ENABLE_TABLES | pulldown_cmark::Options::ENABLE_STRIKETHROUGH,
        ),
    );
    // Удалённые картинки не подгружаем автоматически из ответа провайдера.
    ammonia::Builder::default()
        .rm_tags(&["img"])
        .clean(&html)
        .to_string()
}

#[component]
pub fn build_message(message: StoredMessage) -> Element {
    let state = use_context::<Signal<AppState>>();
    let mut state = state;
    let mut actions = use_signal(|| false);
    let mut editing = use_signal(|| false);
    let mut text = use_signal(|| message.content.clone());
    let mut deleting = use_signal(|| false);
    let id = message.id;
    let active = state.read().active;
    let busy = state.read().busy;
    let user = message.role == "user";
    let copy_text = message.content.clone();
    rsx! {
        article { class: if user { "message user" } else { "message assistant" },
            div { class: "message-bubble",
            if let Some(quote) = message.quote { blockquote { "{quote}" } }
            if *editing.read() {
                textarea { class: "editor", "aria-label": "Текст сообщения", value: "{text}", oninput: move |e| text.set(e.value()) }
                div { class: "row",
                    button { class: "button", onclick: move |_| { spawn(async move {
                        let result = async {
                            let store = state::store(state)?;
                            let content = text.read().clone();
                            services::runtime::background(async move { store.run(move |db| { db.update_message(id, &content)?; Ok(()) }).await }).await?;
                            state::refresh(state, active).await?;
                            editing.set(false);
                            Ok(())
                        }.await;
                        state::report(state, result);
                    }); }, "Сохранить" }
                    button { class: "button", onclick: move |_| editing.set(false), "Отмена" }
                }
            } else if user { div { "{message.content}" } }
            else { div { class: "markdown", dangerous_inner_html: markdown_html(&message.content) } }
            if !message.attachments.is_empty() {
                div { class: "files", for (name, _) in message.attachments { span { class: "attachment", icons::build_icon { name: "description" } "{name}" } } }
            }
            }
            div { class: "message-footer",
                button { class: "message-action", title: "Копировать", "aria-label": "Копировать", onclick: move |_| {
                    let text = serde_json::to_string(&copy_text).unwrap_or_default();
                    spawn(async move {
                        let script = format!(r#"const text={text};
                            try {{ if(navigator.clipboard) {{ await navigator.clipboard.writeText(text); return true; }} }} catch (_) {{}}
                            const before=document.activeElement, area=document.createElement('textarea');
                            area.value=text; area.style.position='fixed'; area.style.left='-10000px';
                            document.body.appendChild(area); area.select();
                            const copied=document.execCommand('copy'); area.remove(); before?.focus({{preventScroll:true}});
                            if(!copied) throw new Error('Буфер обмена недоступен'); return true;"#);
                        match document::eval(&script).await {
                            Ok(_) => state.write().notice = Some("Скопировано".into()),
                            Err(_) => state.write().error = Some("Не удалось скопировать текст в буфер обмена".into()),
                        }
                    });
                }, icons::build_icon { name: "content_copy" } }
                div { class: "message-action-menu",
                    button { class: "message-action", title: "Действия сообщения", "aria-label": "Действия сообщения", onclick: move |_| { let open = *actions.read(); actions.set(!open); }, icons::build_icon { name: "more_horiz" } }
                    if *actions.read() {
                        div { class: "message-popup",
                            button { class: "popup-item", onclick: { let content = message.content.clone(); move |_| { actions.set(false); let mut value = state.write(); if !value.draft.text.is_empty() { value.draft.text.push_str("\n\n"); } value.draft.text.push_str(&format!("> {}\n\n", content.replace('\n', "\n> "))); } }, icons::build_icon { name: "format_quote" } "Цитировать" }
                            button { class: "popup-item", disabled: busy, onclick: move |_| { actions.set(false); editing.set(true); }, icons::build_icon { name: "edit" } "Изменить" }
                            button { class: "popup-item danger", disabled: busy, onclick: move |_| { actions.set(false); deleting.set(true); }, icons::build_icon { name: "delete_outline" } "Удалить" }
                        }
                    }
                }
                if let Some(seconds) = message.elapsed_seconds { span { class: "message-duration", "Время ответа · {seconds:.1} с" } }
            }
            if *deleting.read() {
                div { class: "row",
                    span { "Удалить сообщение?" }
                    button { class: "button danger", onclick: move |_| { spawn(async move {
                        let result = async {
                            let store = state::store(state)?;
                            services::runtime::background(async move { store.run(move |db| { db.delete_message(id)?; Ok(()) }).await }).await?;
                            state::refresh(state, active).await
                        }.await;
                        state::report(state, result);
                    }); }, "Да" }
                    button { class: "button", onclick: move |_| deleting.set(false), "Отмена" }
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn markdown_cannot_run_scripts_or_load_tracking_images() {
        let html = markdown_html(
            "# Hello\n<script>alert(1)</script>\n<img src='https://tracker.test/pixel'>\n[x](javascript:alert(1))",
        );
        assert!(html.contains("<h1>"));
        assert!(!html.contains("<script"));
        assert!(!html.contains("<img"));
        assert!(!html.contains("href=\"javascript:"));
    }
}
