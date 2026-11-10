// Файл: App/app/canvas/canvas_editor.rs
// Описание: Текст, код и изолированный HTML-предпросмотр.
use crate::app::shared::icons;
use crate::{
    app::state::{self, AppState},
    services::{
        self,
        canvases::{self, Document},
    },
};
use dioxus::prelude::*;

#[component]
pub fn build_canvas_dialog() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let mut docs = use_signal(Vec::<Document>::new);
    let mut current = use_signal(|| Document {
        kind: "text".into(),
        ..Default::default()
    });
    let mut revision = use_signal(|| 0u64);
    let mut status = use_signal(String::new);
    let mut dirty = use_signal(|| false);
    let mut pending = use_signal(|| None::<Document>);
    use_effect(move || state.write().unsaved = *dirty.read());
    use_drop(move || state.write().unsaved = false);
    let _load = use_resource(move || {
        let _revision = *revision.read();
        async move {
            let result = async {
                let store = state::store(state)?;
                docs.set(
                    services::runtime::blocking(move || canvases::list_documents(&store)).await?,
                );
                Ok(())
            }
            .await;
            state::report(state, result);
        }
    });
    let document = current.read().clone();
    rsx! {
        div { class: "page", div { class: "page-content",
            div { class: "canvas-document-row",
                label { class: "field", "Документ", select { "aria-label": "Документ", value: "{document.id}", onchange: move |e| {
                    let id = e.value();
                    let selected = docs.read().iter().find(|doc| doc.id == id).cloned();
                    if let Some(selected) = selected {
                        if *dirty.read() { pending.set(Some(selected)); } else { current.set(selected); }
                    }
                },
                    option { value: "", "Новый документ" }
                    for doc in docs.read().iter() { option { value: "{doc.id}", "{doc.title}" } }
                } }
                button { class: "plain-icon", title: "Новый Canvas", onclick: move |_| {
                    let new = Document { kind: "text".into(), chat_id: state.read().active, ..Default::default() };
                    if *dirty.read() { pending.set(Some(new)); }
                    else { current.set(new); }
                }, icons::build_icon { name: "add" } }
            }
            if pending.read().is_some() {
                div { class: "section row", role: "alert", "Есть несохранённый текст. Переключить документ?"
                    button { class: "button danger", onclick: move |_| { let next = pending.write().take(); if let Some(next) = next { current.set(next); dirty.set(false); } }, "Отбросить изменения" }
                    button { class: "button", onclick: move |_| pending.set(None), "Продолжить редактирование" }
                }
            }
            section { class: "section",
                label { class: "field", "Название", input { value: "{document.title}", oninput: move |e| { current.write().title = e.value(); dirty.set(true); } } }
                label { class: "field", "Вид", select { value: "{document.kind}", onchange: move |e| { current.write().kind = e.value(); dirty.set(true); },
                    option { value: "text", "Текст / Markdown" } option { value: "code", "Код" } option { value: "web", "HTML-сайт" }
                    if document.kind == "drawing" { option { value: "drawing", "Рисунок прежней версии" } }
                } }
                if document.kind == "drawing" {
                    p { class: "notice", "Рисунок сохранён в базе. Редактор рисования ещё не перенесён." }
                } else {
                    textarea { class: "editor", "aria-label": "Содержимое Canvas", value: "{document.content}", oninput: move |e| { current.write().content = e.value(); dirty.set(true); } }
                }
                div { class: "row",
                    button { class: "button primary", onclick: move |_| { spawn(async move {
                        let result = async {
                            let store = state::store(state)?;
                            let value = current.read().clone();
                            let saved = services::runtime::blocking(move || canvases::save_document(&store, value)).await?;
                            current.set(saved); dirty.set(false); revision += 1; status.set("Canvas сохранён".into()); Ok(())
                        }.await;
                        state::report(state, result);
                    }); }, "Сохранить" }
                    if *dirty.read() { span { class: "notice", "Есть несохранённые изменения" } }
                }
                p { class: "notice", role: "status", "{status}" }
            }
            if document.kind == "web" {
                iframe { class: "preview", title: "Предпросмотр Canvas", "sandbox": "", referrerpolicy: "no-referrer", srcdoc: format!("<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:;\">{}", document.content) }
            } else if document.kind == "text" {
                section { class: "section markdown", dangerous_inner_html: crate::app::chat::messages::message::markdown_html(&document.content) }
            }
        } }
    }
}
