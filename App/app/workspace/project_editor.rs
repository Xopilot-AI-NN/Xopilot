// Описание: Поиск, чтение, Git и сохранение с обнаружением внешних правок.
use crate::{
    app::state::{self, AppState},
    services::{self, project_inspection, project_tools, workspaces::Workspace},
};
use dioxus::prelude::*;
use std::path::PathBuf;

#[component]
pub fn build_project_editor(workspace: Workspace) -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let mut path = use_signal(String::new);
    let mut content = use_signal(String::new);
    let mut original = use_signal(String::new);
    let mut opened_path = use_signal(String::new);
    let mut query = use_signal(String::new);
    let mut output = use_signal(String::new);
    let mut dirty = use_signal(|| false);
    let mut closing = use_signal(|| false);
    use_effect(move || state.write().unsaved = *dirty.read());
    use_drop(move || state.write().unsaved = false);
    let root = PathBuf::from(&workspace.folder);
    rsx! {
        section { class: "section",
            h2 { "Файлы · {workspace.name}" }
            div { class: "row",
                button { class: "button", onclick: { let root = root.clone(); move |_| { let root = root.clone(); spawn(async move {
                    let result = async {
                        output.set(services::runtime::blocking(move || Ok(project_inspection::list_files(&root)?.join("\n"))).await?); Ok(())
                    }.await; state::report(state, result);
                }); } }, "Список файлов" }
                button { class: "button", onclick: { let root = root.clone(); move |_| { let root = root.clone(); spawn(async move {
                    let result = async {
                        output.set(services::runtime::background(async move { project_inspection::git(&root, false).await }).await?); Ok(())
                    }.await; state::report(state, result);
                }); } }, "Git status" }
                button { class: "button", onclick: { let root = root.clone(); move |_| { let root = root.clone(); spawn(async move {
                    let result = async {
                        output.set(services::runtime::background(async move { project_inspection::git(&root, true).await }).await?); Ok(())
                    }.await; state::report(state, result);
                }); } }, "Git diff --stat" }
            }
            label { class: "field", "Поиск по коду", input { value: "{query}", oninput: move |e| query.set(e.value()) } }
            button { class: "button", onclick: { let root = root.clone(); move |_| { let root = root.clone(); spawn(async move {
                let result = async {
                    let q = query.read().clone();
                    output.set(services::runtime::blocking(move || Ok(project_inspection::search(&root, &q)?.iter().map(|h| format!("{}:{}: {}", h.path, h.line, h.text)).collect::<Vec<_>>().join("\n"))).await?); Ok(())
                }.await; state::report(state, result);
            }); } }, "Найти" }
            if !output.read().is_empty() { pre { class: "code", "{output}" } }
            label { class: "field", "Относительный путь файла", input { value: "{path}", placeholder: "src/main.rs", oninput: move |e| path.set(e.value()) } }
            button { class: "button", disabled: *dirty.read(), onclick: { let root = root.clone(); move |_| { let root = root.clone(); spawn(async move {
                let result = async {
                    let relative = path.read().clone();
                    let opened = relative.clone();
                    let text = services::runtime::blocking(move || project_inspection::read_text(&root, &relative)).await?;
                    original.set(project_tools::fingerprint(&text)); content.set(text); opened_path.set(opened); dirty.set(false); Ok(())
                }.await; state::report(state, result);
            }); } }, "Открыть файл" }
            if !opened_path.read().is_empty() {
                p { class: "notice", "Редактируется: {opened_path}" }
                textarea { class: "editor", "aria-label": "Редактор файла", value: "{content}", oninput: move |e| { content.set(e.value()); dirty.set(true); } }
                div { class: "row",
                    button { class: "button primary", disabled: !*dirty.read(), onclick: { let root = root.clone(); move |_| { let root = root.clone(); spawn(async move {
                        let result = async {
                            let relative = opened_path.read().clone(); let text = content.read().clone(); let expected = original.read().clone();
                            let fingerprint = services::runtime::blocking(move || project_tools::save_existing(&root, &relative, &text, &expected)).await?;
                            original.set(fingerprint); dirty.set(false); Ok(())
                        }.await; state::report(state, result);
                    }); } }, "Сохранить файл" }
                    if *dirty.read() { span { class: "notice", "Есть несохранённые изменения" } }
                    button { class: "button", onclick: move |_| {
                        if *dirty.read() { closing.set(true); }
                        else { opened_path.set(String::new()); }
                    }, "Закрыть редактор" }
                }
                if *closing.read() {
                    div { class: "row", role: "alert",
                        span { "Отбросить несохранённые изменения файла?" }
                        button { class: "button danger", onclick: move |_| { content.set(String::new()); opened_path.set(String::new()); original.set(String::new()); dirty.set(false); closing.set(false); }, "Отбросить" }
                        button { class: "button", onclick: move |_| closing.set(false), "Продолжить редактирование" }
                    }
                }
            }
        }
    }
}
