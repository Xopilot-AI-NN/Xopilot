// Описание: Возвращаем hero, логотип, описание и компактные чипы прежней страницы.
use crate::{
    app::{
        shared::icons,
        state::{self, AppState},
    },
    services,
};
use dioxus::prelude::*;

#[component]
/// Показывает назначение приложения, локальные возможности, версию и разработчика.
pub fn build_info() -> Element {
    let state = use_context::<Signal<AppState>>();
    let version = env!("CARGO_PKG_VERSION");
    rsx! {
        div {
            class: "about-page",
            div {
                class: "about-brand",
                div {
                    class: "about-logo",
                    img {
                        src: crate::app::shared::static_assets::ICON,
                        alt: "Логотип Xopilot",
                    }
                }
                h2 {
                    "Xopilot"
                }
                p {
                    class: "notice",
                    "Чаты, материалы и ИИ · DenBroLiik"
                }
            }
            p {
                class: "about-description",
                "Твой ИИ. Твои проекты. Твои устройства."
            }
            p {
                class: "notice about-description",
                "Автономное пространство для разговоров, работы с материалами и локальной моделью. Зашифрованная история остаётся на устройстве."
            }
            div {
                class: "about-chips",
                span {
                    "Версия {version}"
                }
                span {
                    "Rust · Dioxus · LiteRT-LM"
                }
                span {
                    icons::build_icon {
                        name: "lock_outline",
                    }
                    "SQLCipher"
                }
                span {
                    "Linux · Android"
                }
            }
            div {
                class: "about-features",
                section {
                    icons::build_icon {
                        name: "smart_toy_outlined",
                    }
                    h3 {
                        "Рядом с твоими данными"
                    }
                    p {
                        "Локальные модели, материалы и история без обязательного облака."
                    }
                }
                section {
                    icons::build_icon {
                        name: "workspaces",
                    }
                    h3 {
                        "От идеи к результату"
                    }
                    p {
                        "Проекты, документы Canvas и агент с понятными действиями в чате."
                    }
                }
            }
            div {
                class: "about-developer",
                icons::build_icon {
                    name: "code",
                }
                div {
                    strong {
                        "DenBroLiik"
                    }
                    small {
                        "Разработчик · Лицензия MIT"
                    }
                }
                button {
                    class: "button",
                    onclick: move |_| state::report(
                        state,
                        services::platform_links::open("https://github.com/Xopilot-AI-NN/Xopilot"),
                    ),
                    "Исходный код"
                }
            }
        }
    }
}
