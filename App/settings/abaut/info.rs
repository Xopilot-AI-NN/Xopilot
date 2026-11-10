// Описание: Название папки abaut оставлено по структуре прежнего приложения.
use crate::app::shared::icons;
use dioxus::prelude::*;

#[component]
pub fn build_info() -> Element {
    rsx! {
        div { class: "about-hero", icons::build_icon { name: "auto_awesome" } h2 { "Xopilot" } p { "Твой ИИ. Твои проекты. Твои устройства." } }
        div { class: "settings-card", icons::build_icon { name: "info_outline" } div { strong { "Версия 2.1.0" } p { class: "notice", "Rust / Dioxus" } } }
        div { class: "settings-card", icons::build_icon { name: "code" } div { strong { "DenBroLiik" } p { class: "notice", "Разработчик · Лицензия MIT" } } }
        p { class: "notice", "Часть возможностей прежней версии ещё переносится. Статус доступности указан в соответствующих разделах." }
    }
}
