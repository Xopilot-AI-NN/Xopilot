// Файл: App/settings/main.rs
// Описание: Домашняя страница и разделы настроек из Flet-версии.
use crate::{
    app::{
        chat::chats,
        dialogs,
        shared::{dialog, icons},
        state::{self, AppState, Screen},
    },
    settings::{abaut, personalizations},
};
use dioxus::prelude::*;

const SECTIONS: &[(&str, &str, &str)] = &[
    (
        "person_outline",
        "Профиль и аккаунт",
        "Имя и статистика использования",
    ),
    (
        "tune",
        "Персонализация",
        "Тема, язык, модели ИИ и голос Live",
    ),
    (
        "download_outlined",
        "Модели",
        "Загрузка Gemma 4 и голосов Live",
    ),
    ("history", "История", "Удаление и управление сообщениями"),
    (
        "system_update_outlined",
        "Обновления",
        "Версия и обновления приложения",
    ),
    (
        "info_outline",
        "О программе",
        "Версия, описание и разработчик",
    ),
];

#[component]
pub fn build_settings_dialog() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let selected = state.read().settings_section;
    let title = selected
        .map(|index| SECTIONS[index].1)
        .unwrap_or("Настройки");
    let back = selected.map(|_| EventHandler::new(move |_| state.write().settings_section = None));
    rsx! {
        dialog::build_dialog { title, settings: true, back,
            if let Some(index) = selected {
                match index {
                    0 => rsx! { personalizations::main::build_personalizations { account: true } },
                    1 => rsx! { personalizations::main::build_personalizations {} },
                    2 => rsx! { dialogs::build_model_catalog {} },
                    3 => rsx! { chats::build_chats_dialog {} },
                    4 => rsx! { self::build_updates {} },
                    _ => rsx! { abaut::info::build_info {} },
                }
            } else {
                h2 { class: "section-title", "Параметры приложения" }
                nav { class: "settings-navigation", for (index, &(icon, label, subtitle)) in SECTIONS.iter().enumerate() {
                    button { class: "settings-navigation-row", onclick: move |_| state.write().settings_section = Some(index),
                        span { class: "settings-badge tone-navigate", icons::build_icon { name: icon } }
                        span { class: "settings-row-copy", strong { "{label}" } small { "{subtitle}" } }
                        icons::build_icon { name: "chevron_right" }
                    }
                } }
            }
        }
    }
}

#[component]
fn build_updates() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    rsx! {
        h2 { class: "section-title", "Версия приложения" }
        div { class: "settings-card", icons::build_icon { name: "system_update_outlined" } div { strong { "Xopilot 2.1.0" } p { class: "notice", "Установленная версия" } } }
        button { class: "button", onclick: move |_| state.write().notice = Some("Проверка и установка обновлений ещё переносятся.".into()), "Проверить обновления" }
        button { class: "button", onclick: move |_| state::navigate(state, Screen::Api), "Настроить API" }
    }
}
