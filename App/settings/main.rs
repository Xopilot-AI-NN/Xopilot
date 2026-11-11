// Файл: App/settings/main.rs
// Описание: Домашняя страница и разделы настроек.
use crate::{
    app::{
        chat::chats,
        dialogs,
        shared::{dialog, icons},
        state::{self, AppState},
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
    let state = use_context::<Signal<AppState>>();
    let selected = state.read().settings_section;
    let title = selected
        .map(|index| SECTIONS[index].1)
        .unwrap_or("Настройки");
    let back =
        selected.map(|_| EventHandler::new(move |_| state::select_settings_section(state, None)));
    rsx! {
        dialog::build_dialog { title, settings: true, immediate: true, back,
            if let Some(index) = selected {
                match index {
                    0 => rsx! { crate::settings::account::main::build_account_page {} },
                    1 => rsx! { personalizations::main::build_personalizations {} },
                    2 => rsx! { dialogs::build_model_catalog {} },
                    3 => rsx! { chats::build_chats_dialog {} },
                    4 => rsx! { crate::settings::updates::main::build_updates {} },
                    _ => rsx! { abaut::info::build_info {} },
                }
            } else {
                h2 { class: "section-title", "Параметры приложения" }
                nav { class: "settings-navigation", for (index, &(icon, label, subtitle)) in SECTIONS.iter().enumerate() {
                    button { class: "settings-navigation-row", onclick: move |_| state::select_settings_section(state, Some(index)),
                        span { class: "settings-badge tone-navigate", icons::build_icon { name: icon } }
                        span { class: "settings-row-copy", strong { "{label}" } small { "{subtitle}" } }
                        icons::build_icon { name: "chevron_right" }
                    }
                } }
            }
        }
    }
}
