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

/// Редактирует документы Canvas с защитой несохранённых и внешних изменений.
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
    let mut deleting = use_signal(|| false);
    use_effect(move || {
        state.write().unsaved = *dirty.read()
    });
    use_drop(move || state.write().unsaved = false);
    let _load = use_resource(move || {
        let _revision = *revision.read();
        async move {
            let result = async {
                let store = state::store(state)?;
                docs.set(
                    services::runtime::blocking(
                        move || {
                            canvases::list_documents(&store)
                        },
                    )
                    .await?,
                );
                Ok(())
            }
            .await;
            state::report(state, result);
        }
    });
    let document = current.read().clone();
    rsx! {
        div {
            class: "page",
            div {
                class: "page-content",
                div {
                    class: "canvas-document-row",
                    label {
                        class: "field",
                        "Документ"
                        crate::app::shared::select::build_select {
                            id: "canvas-document",
                            label: "Документ",
                            value: document.id.clone(),
                            options: std::iter::once((String::new(), "Новый документ".to_owned()))
                                .chain(docs.read().iter().map(|doc| (doc.id.clone(), doc.title.clone())))
                                .collect::<Vec<_>>(),
                            onchange: move |id: String| {
                                let selected = if id.is_empty() {
                                    Some(Document {
                                        kind: "text".into(),
                                        chat_id: state.read().active,
                                        ..Default::default()
                                    })
                                } else {
                                    docs.read().iter().find(|doc| doc.id == id).cloned()
                                };
                                if let Some(selected) = selected {
                                    if *dirty.read() {
                                        pending.set(Some(selected));
                                    } else {
                                        current.set(selected);
                                        status.set(String::new());
                                        deleting.set(false);
                                    }
                                }
                            },
                        }
                    }
                    button {
                        class: "plain-icon",
                        title: "Новый Canvas",
                        onclick: move |_| {
                            let new = Document {
                                kind: "text".into(),
                                chat_id: state.read().active,
                                ..Default::default()
                            };
                            if *dirty.read() {
                                pending.set(Some(new));
                            } else {
                                current.set(new);
                            }
                        },
                        icons::build_icon {
                            name: "add",
                        }
                    }
                }
                if pending.read().is_some() {
                    div {
                        class: "section row",
                        role: "alert",
                        "Есть несохранённый текст. Переключить документ?"
                        button {
                            class: "button danger",
                            onclick: move |_| {
                                let next = pending.write().take();
                                if let Some(next) = next {
                                    current.set(next);
                                    dirty.set(false);
                                }
                            },
                            "Отбросить изменения"
                        }
                        button {
                            class: "button",
                            onclick: move |_| pending.set(None),
                            "Продолжить редактирование"
                        }
                    }
                }
                section {
                    class: "section",
                    label {
                        class: "field",
                        "Название"
                        input {
                            value: "{document.title}",
                            oninput: move |e| {
                                current.write().title = e.value();
                                dirty.set(true);
                            },
                        }
                    }
                    label {
                        class: "field",
                        "Вид"
                        crate::app::shared::select::build_select {
                            id: "canvas-kind",
                            label: "Вид Canvas",
                            value: document.kind.clone(),
                            options: {
                                let mut options = vec![
                                    ("text".into(), "Текст / Markdown".into()),
                                    ("code".into(), "Код".into()),
                                    ("web".into(), "HTML-сайт".into()),
                                ];
                                if document.kind == "drawing" {
                                    options
                                        .push((
                                            "drawing".into(),
                                            "Рисунок прежней версии".into(),
                                        ));
                                }
                                options
                            },
                            onchange: move |kind: String| {
                                current.write().kind = kind;
                                dirty.set(true);
                            },
                        }
                    }
                    if document.kind == "drawing" {
                        p {
                            class: "notice",
                            "Рисунок сохранён в базе. Редактор рисования ещё не перенесён."
                        }
                    } else {
                        textarea {
                            class: "editor",
                            "aria-label": "Содержимое Canvas",
                            value: "{document.content}",
                            oninput: move |e| {
                                current.write().content = e.value();
                                dirty.set(true);
                            },
                        }
                    }
                    div {
                        class: "row",
                        button {
                            class: "button primary",
                            onclick: move |_| {
                                spawn(async move {
                                    let result = async {
                                        let store = state::store(state)?;
                                        let value = current.read().clone();
                                        let saved = services::runtime::blocking(move || canvases::save_document(
                                                &store,
                                                value,
                                            ))
                                            .await?;
                                        current.set(saved);
                                        dirty.set(false);
                                        revision += 1;
                                        status.set("Canvas сохранён".into());
                                        Ok(())
                                    }
                                        .await;
                                    state::report(state, result);
                                });
                            },
                            "Сохранить"
                        }
                        if *dirty.read() {
                            span {
                                class: "notice",
                                "Есть несохранённые изменения"
                            }
                        }
                        for format in ["docx", "xlsx"] {
                            button {
                                class: "button",
                                onclick: move |_| {
                                    let document = current.read().clone();
                                    spawn(async move {
                                        let result = services::runtime::blocking(move || {
                                            services::office::save(&document.title, &document.content, format)
                                        }).await;
                                        match result {
                                            Ok(path) => status.set(format!("Документ сохранён: {}", path.display())),
                                            Err(error) => state::report(state, Err(error)),
                                        }
                                    });
                                },
                                "Экспорт {format}"
                            }
                        }
                        if !document.id.is_empty() {
                            button {
                                class: "button danger",
                                onclick: move |_| deleting.set(true),
                                "Удалить Canvas"
                            }
                        }
                    }
                    if *deleting.read() {
                        div {
                            class: "section",
                            role: "alert",
                            p {
                                "Удалить этот Canvas вместе с несохранёнными изменениями?"
                            }
                            div {
                                class: "row",
                                button {
                                    class: "button",
                                    onclick: move |_| deleting.set(false),
                                    "Отмена"
                                }
                                button {
                                    class: "button danger",
                                    onclick: move |_| {
                                        spawn(async move {
                                            let result = async {
                                                let store = state::store(state)?;
                                                let id = current.peek().id.clone();
                                                services::runtime::blocking(move || canvases::delete_document(
                                                        &store,
                                                        &id,
                                                    ))
                                                    .await?;
                                                current
                                                    .set(Document {
                                                        kind: "text".into(),
                                                        chat_id: state.peek().active,
                                                        ..Default::default()
                                                    });
                                                dirty.set(false);
                                                deleting.set(false);
                                                revision += 1;
                                                status.set("Canvas удалён".into());
                                                Ok(())
                                            }
                                                .await;
                                            state::report(state, result);
                                        });
                                    },
                                    "Подтвердить удаление Canvas"
                                }
                            }
                        }
                    }
                    p {
                        class: "notice",
                        role: "status",
                        "{status}"
                    }
                }
                if document.kind == "web" {
                    iframe {
                        class: "preview",
                        title: "Предпросмотр Canvas",
                        "sandbox": "",
                        referrerpolicy: "no-referrer",
                        srcdoc: format!(
                            "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:;\">{}",
                            document.content,
                        ),
                    }
                } else if document.kind == "text" {
                    section {
                        class: "section markdown",
                        dangerous_inner_html: crate::app::chat::messages::message::markdown_html(&document.content),
                    }
                }
            }
        }
    }
}
