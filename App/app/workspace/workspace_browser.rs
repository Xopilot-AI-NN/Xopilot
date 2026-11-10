// Файл: App/app/workspace/workspace_browser.rs
// Описание: Проекты с инструкциями, папкой и привязкой текущего чата.
use super::project_editor;
use crate::app::shared::icons;
use crate::{
    app::state::{self, AppState},
    services::{
        self,
        workspaces::{self, Workspace, Workspaces},
    },
};
use dioxus::prelude::*;

#[component]
pub fn build_workspaces_dialog() -> Element {
    let state = use_context::<Signal<AppState>>();
    let mut data = use_signal(Workspaces::default);
    let mut current = use_signal(Workspace::default);
    let mut editing = use_signal(|| false);
    let mut query = use_signal(String::new);
    let mut revision = use_signal(|| 0u64);
    let mut editor = use_signal(|| None::<Workspace>);
    let mut status = use_signal(String::new);
    let mut dirty = use_signal(|| false);
    let mut deleting = use_signal(|| None::<String>);
    // Редактор файлов имеет собственную защиту; формы не открываем поверх его правок.
    use_effect(move || {
        if *editing.read() {
            let mut state = state;
            state.write().unsaved = *dirty.read();
        }
    });
    use_drop(move || {
        let mut state = state;
        if let Ok(mut value) = state.try_write() {
            value.unsaved = false;
        }
    });
    let _load = use_resource(move || {
        let _revision = *revision.read();
        async move {
            let result = async {
                let store = state::store(state)?;
                data.set(
                    services::runtime::blocking(move || workspaces::list_workspaces(&store))
                        .await?,
                );
                Ok(())
            }
            .await;
            state::report(state, result);
        }
    });
    let item = current.read().clone();
    let needle = query.read().to_lowercase();
    let items: Vec<_> = data
        .read()
        .items
        .iter()
        .filter(|w| w.name.to_lowercase().contains(&needle))
        .cloned()
        .collect();
    let active = state.read().active;
    let assigned = active.and_then(|id| data.read().chats.get(&id.to_string()).cloned());
    rsx! {
        div { class: "page", div { class: "page-content",
            div { class: "row row-between", h1 { "Проекты" }
                button { class: "button", disabled: state.read().unsaved, onclick: move |_| { current.set(Workspace::default()); editing.set(true); }, icons::build_icon { name: "add" } "Новое пространство" }
            }
            label { class: "outlined-search", icons::build_icon { name: "search" } input { value: "{query}", placeholder: "Поиск пространств", oninput: move |e| query.set(e.value()) } }
            if *editing.read() { section { class: "section",
                label { class: "field", "Название", input { value: "{item.name}", oninput: move |e| { current.write().name = e.value(); dirty.set(true); } } }
                label { class: "field", "Инструкции для модели", textarea { value: "{item.instructions}", oninput: move |e| { current.write().instructions = e.value(); dirty.set(true); } } }
                label { class: "field", "Путь к папке на этом устройстве", input { value: "{item.folder}", placeholder: "/home/user/project", oninput: move |e| { current.write().folder = e.value(); dirty.set(true); } } }
                p { class: "notice", "Папка необязательна. На Android доступны каталоги приложения; произвольный путь к общей памяти может быть недоступен." }
                button { class: "button primary", onclick: move |_| { spawn(async move {
                    let result = async {
                        let store = state::store(state)?;
                        let item = current.read().clone();
                        services::runtime::blocking(move || workspaces::save_workspace(&store, item)).await?;
                        current.set(Workspace::default()); dirty.set(false); let mut state = state; state.write().unsaved = false; editing.set(false); revision += 1; status.set("Пространство сохранено".into()); state::refresh(state, active).await?; Ok(())
                    }.await;
                    state::report(state, result);
                }); }, "Сохранить проект" }
                button { class: "button", onclick: move |_| { dirty.set(false); let mut state = state; state.write().unsaved = false; editing.set(false); }, "Отмена" }
                p { class: "notice", role: "status", "{status}" }
            }
            }
            button { class: "catalog-row workspace-all", disabled: state.read().unsaved, onclick: move |_| state::navigate(state, crate::app::state::Screen::Chats),
                span { class: "workspace-icon", icons::build_icon { name: "folder_open" } }
                span { class: "catalog-copy", strong { "Все чаты" } small { "{state.read().chats.len()} чатов" } }
            }
            div { class: "list", for workspace in items {
                section { class: "section", key: "{workspace.id}",
                    h2 { "{workspace.name}" }
                    p { class: "notice", "{workspace.instructions}" }
                    if !workspace.folder.is_empty() { p { class: "notice", "{workspace.folder}" } }
                    div { class: "row",
                        button { class: "button", disabled: state.read().unsaved, onclick: { let workspace = workspace.clone(); move |_| { current.set(workspace.clone()); editing.set(true); } }, "Изменить" }
                        button { class: "button danger", disabled: state.read().unsaved, onclick: { let id = workspace.id.clone(); move |_| deleting.set(Some(id.clone())) }, "Удалить пространство" }
                        button { class: "button", onclick: { let workspace = workspace.clone(); move |_| {
                            let id = workspace.id.clone();
                            spawn(async move {
                                let result = async {
                                    let store = state::store(state)?;
                                    let chat = active.ok_or_else(|| anyhow::anyhow!("Выберите чат"))?;
                                    services::runtime::blocking(move || workspaces::assign_chat(&store, chat, &id)).await?;
                                    revision += 1; state::refresh(state, active).await?; status.set("Чат привязан к проекту".into()); Ok(())
                                }.await;
                                state::report(state, result);
                            });
                        } },
                            if assigned.as_deref() == Some(workspace.id.as_str()) { "✓ Текущий чат в проекте" } else { "Привязать текущий чат" }
                        }
                        if !workspace.folder.is_empty() {
                            button { class: "button", disabled: state.read().unsaved || *editing.read(), onclick: { let workspace = workspace.clone(); move |_| editor.set(Some(workspace.clone())) }, "Открыть файлы" }
                        }
                    }
                }
            } }
            if let Some(id) = deleting.read().clone() {
                section { class: "section", role: "alert",
                    p { "Удалить пространство? Чаты и файлы на устройстве сохранятся." }
                    div { class: "row",
                        button { class: "button", onclick: move |_| deleting.set(None), "Отмена" }
                        button { class: "button danger", onclick: move |_| { let id = id.clone(); spawn(async move {
                            let result = async {
                                let store = state::store(state)?;
                                services::runtime::blocking(move || workspaces::delete_workspace(&store, &id)).await?;
                                deleting.set(None); editor.set(None); revision += 1; state::refresh(state, active).await?; Ok(())
                            }.await;
                            state::report(state, result);
                        }); }, "Подтвердить удаление пространства" }
                    }
                }
            }
            if let Some(workspace) = editor.read().clone() {
                project_editor::build_project_editor { key: "{workspace.id}", workspace }
            }
        } }
    }
}
