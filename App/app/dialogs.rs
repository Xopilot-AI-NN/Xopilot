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

/// Открывает выбранное окно поверх сохранённого чата.
#[component]
pub fn build_overlay() -> Element {
    let state = use_context::<Signal<AppState>>();
    match state.read().screen {
        Screen::Chat => rsx! {},
        Screen::Settings => rsx! {
            settings::main::build_settings_dialog {
            }
        },
        Screen::Memory => {
            rsx! {
                dialog::build_dialog {
                    title: "Память обо мне",
                    settings: true,
                    immediate: false,
                    back: Some(EventHandler::new(move |_| state::dismiss(state))),
                    settings::personalizations::main::build_personalizations {
                        memory_only: true,
                    }
                }
            }
        }
        Screen::Account => {
            rsx! {
                dialog::build_dialog {
                    title: "Профиль и аккаунт",
                    settings: true,
                    immediate: true,
                    back: Some(EventHandler::new(move |_| state::dismiss(state))),
                    settings::account::main::build_account_page {
                    }
                }
            }
        }
        Screen::Workspaces => {
            rsx! {
                dialog::build_dialog {
                    title: "Рабочие пространства",
                    variant: "workspaces",
                    workspace::workspace_browser::build_workspaces_dialog {
                    }
                }
            }
        }
        Screen::Canvas => {
            rsx! {
                dialog::build_dialog {
                    title: "Canvas",
                    variant: "canvas",
                    canvas::canvas_editor::build_canvas_dialog {
                    }
                }
            }
        }
        Screen::Templates => {
            rsx! {
                dialog::build_dialog {
                    title: "Мои шаблоны",
                    variant: "templates",
                    chat::composer::prompt_templates::build_templates {
                    }
                }
            }
        }
        Screen::Chats => {
            rsx! {
                dialog::build_dialog {
                    title: "Чаты",
                    variant: "chats",
                    chat::chats::build_chats_dialog {
                    }
                }
            }
        }
        Screen::Model => {
            rsx! {
                dialog::build_dialog {
                    title: "Модель чата",
                    variant: "models",
                    narrow: true,
                    self::build_model_catalog {
                    }
                }
            }
        }
        Screen::Api => {
            rsx! {
                dialog::build_dialog {
                    title: "Подключение API",
                    narrow: true,
                    api_settings::build_api_settings {
                    }
                }
            }
        }
        Screen::Materials => {
            rsx! {
                dialog::build_dialog {
                    title: "Материалы",
                    crate::app::materials::main::build_materials {
                    }
                }
            }
        }
        Screen::Private => rsx! {
            dialog::build_dialog {
                title: "Защищённые чаты",
                narrow: true,
                div {
                    class: "dialog-empty",
                    icons::build_icon {
                        name: "lock_outline",
                    }
                    p {
                        "Защищённые чаты с отдельным паролем пока недоступны в новой версии."
                    }
                    p {
                        class: "muted",
                        "Прежние файлы защищённых чатов сохранены."
                    }
                }
            }
        },
    }
}

/// Собирает каталог моделей с актуальными фазами загрузок.
#[component]
pub fn build_model_catalog() -> Element {
    rsx! {
        crate::settings::models::main::build_model_catalog {
        }
    }
}
