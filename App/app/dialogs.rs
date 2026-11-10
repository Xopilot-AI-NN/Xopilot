// Описание: Окна поверх основного экрана; чат при открытии не размонтируется.
use crate::{
    app::{
        canvas, chat,
        settings::api_settings,
        shared::{dialog, icons},
        state::{self, AppState, Screen},
        workspace,
    },
    settings,
};
use dioxus::prelude::*;

#[component]
pub fn build_overlay() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    match state.read().screen {
        Screen::Chat => rsx! {},
        Screen::Settings => rsx! { settings::main::build_settings_dialog {} },
        Screen::Memory => {
            rsx! { dialog::build_dialog { title: "Память обо мне", settings: true, back: Some(EventHandler::new(move |_| state::dismiss(state))), settings::personalizations::main::build_personalizations { memory_only: true } } }
        }
        Screen::Account => {
            rsx! { dialog::build_dialog { title: "Профиль и аккаунт", settings: true, back: Some(EventHandler::new(move |_| { state.write().screen = Screen::Settings; state.write().settings_section = None; })), settings::personalizations::main::build_personalizations { account: true } } }
        }
        Screen::Workspaces => {
            rsx! { dialog::build_dialog { title: "Рабочие пространства", variant: "workspaces", workspace::workspace_browser::build_workspaces_dialog {} } }
        }
        Screen::Canvas => {
            rsx! { dialog::build_dialog { title: "Canvas", variant: "canvas", canvas::canvas_editor::build_canvas_dialog {} } }
        }
        Screen::Templates => {
            rsx! { dialog::build_dialog { title: "Мои шаблоны", variant: "templates", chat::composer::prompt_templates::build_templates {} } }
        }
        Screen::Chats => {
            rsx! { dialog::build_dialog { title: "Чаты", variant: "chats", chat::chats::build_chats_dialog {} } }
        }
        Screen::Model => {
            rsx! { dialog::build_dialog { title: "Модель чата", narrow: true, self::build_model_catalog {} } }
        }
        Screen::Api => {
            rsx! { dialog::build_dialog { title: "Подключение API", narrow: true, api_settings::build_api_settings {} } }
        }
        Screen::Materials => {
            rsx! { dialog::build_dialog { title: "Материалы", self::build_materials {} } }
        }
        Screen::Private => rsx! { dialog::build_dialog { title: "Защищённые чаты", narrow: true,
            div { class: "dialog-empty", icons::build_icon { name: "lock_outline" }
                p { "Защищённые чаты с отдельным паролем пока недоступны в новой версии." }
                p { class: "muted", "Прежние файлы защищённых чатов сохранены." }
            }
        } },
    }
}

#[component]
pub fn build_model_catalog() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    rsx! {
        div { class: "catalog-list",
            div { class: "catalog-row muted", icons::build_icon { name: "construction" } span { "Zephyr Micro · в разработке" } }
            for (name, size) in [("Gemma4-e2b", "~2.59 GB"), ("Gemma4-e4b", "~3.66 GB")] {
                button { class: "catalog-row", onclick: move |_| state.write().notice = Some("Встроенные локальные модели ещё переносятся. Можно подключить локальный сервер через API.".into()),
                    icons::build_icon { name: "smart_toy" }
                    span { class: "catalog-copy", strong { "{name}" } small { "Скачать · {size}" } }
                    icons::build_icon { name: "download" }
                }
            }
            button { class: "catalog-row", onclick: move |_| state::navigate(state, Screen::Api),
                icons::build_icon { name: "api" } span { "API · настроить подключение" }
            }
            p { class: "notice", "Встроенный локальный runtime ещё не перенесён. API и отдельные локальные серверы доступны." }
        }
    }
}

#[component]
pub fn build_materials() -> Element {
    let state = use_context::<Signal<AppState>>();
    let mut materials = use_signal(Vec::<(String, String)>::new);
    let mut query = use_signal(String::new);
    use_future(move || async move {
        let result = async {
            let store = state::store(state)?;
            let items = crate::services::runtime::blocking(move || {
                store.with(|db| {
                    let mut files = Vec::new();
                    for (id, _, _) in db.list_chats()? {
                        for message in db.get_messages(id)? {
                            files.extend(message.attachments);
                        }
                    }
                    files.sort();
                    files.dedup();
                    Ok(files)
                })
            })
            .await?;
            materials.set(items);
            Ok(())
        }
        .await;
        state::report(state, result);
    });
    let needle = query.read().to_lowercase();
    rsx! {
        label { class: "outlined-search", icons::build_icon { name: "search" } input { placeholder: "Поиск материалов", value: "{query}", oninput: move |e| query.set(e.value()) } }
        div { class: "catalog-list", for (name, path) in materials.read().iter().filter(|(name, _)| name.to_lowercase().contains(&needle)) {
            div { class: "catalog-row", icons::build_icon { name: "description" } span { class: "catalog-copy", strong { "{name}" } small { "{path}" } } }
        } }
        if materials.read().is_empty() { p { class: "notice dialog-empty", "Здесь появятся ваши материалы. Прикрепите файл к сообщению." } }
    }
}
