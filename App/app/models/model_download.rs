// Описание: Компактная карточка модели с действием справа.
use crate::{
    app::{
        shared::icons,
        state::{self, AppState},
    },
    services::{
        self,
        model_installer::{self, Progress},
    },
};
use dioxus::prelude::*;

#[component]
pub fn build_model_row(id: String, progress: Progress) -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let spec = model_installer::model(&id).unwrap();
    let installed = model_installer::installed_path(spec).is_ok();
    let running = ["downloading", "verifying"].contains(&progress.phase.as_str());
    let mut deleting = use_signal(|| false);
    let selected = state.read().model_local && state.read().model == spec.name;
    let status = match progress.phase.as_str() {
        "downloading" => "Загрузка",
        "verifying" => "Проверка SHA-256",
        "paused" => "На паузе",
        "error" => "Ошибка",
        _ => {
            if installed {
                "Установлена"
            } else {
                "Не установлена"
            }
        }
    };
    let mib = progress.downloaded as f64 / 1048576.0;
    rsx! {
        section { class: "model-card",
            div { class: "model-card-main",
                span { class: "model-icon tone-ai",
                    icons::build_icon { name: "smart_toy_outlined" }
                }
                span { class: "catalog-copy",
                    strong { "{spec.name}" }
                    small { "{spec.size} · LiteRT-LM" }
                    span { class: if installed { "model-state installed" } else { "model-state" },
                        "{status}"
                    }
                }
                div { class: "model-card-actions",
                    if running {
                        button {
                            class: "button",
                            onclick: move |_| model_installer::pause(spec.id),
                            "Пауза"
                        }
                    } else if installed {
                        button {
                            class: "button primary",
                            disabled: state.read().busy || selected,
                            onclick: move |_| {
                                spawn(async move {
                                    let result = async {
                                        let store = state::store(state)?;
                                        let name = services::runtime::blocking(move || model_installer::select(
                                                &store,
                                                spec.id,
                                            ))
                                            .await?;
                                        state.write().model = name;
                                        state.write().model_local = true;
                                        Ok(())
                                    }
                                        .await;
                                    state::report(state, result);
                                });
                            },
                            if selected {
                                "Выбрана"
                            } else {
                                "Выбрать"
                            }
                        }
                        button {
                            class: "button danger",
                            disabled: state.read().busy,
                            onclick: move |_| deleting.set(true),
                            "Удалить модель"
                        }
                    } else {
                        button {
                            class: "button",
                            onclick: move |_| state::report(state, model_installer::start(spec.id)),
                            if progress.downloaded > 0 {
                                "Продолжить"
                            } else {
                                "Скачать"
                            }
                        }
                    }
                }
            }
            if running || progress.phase == "paused" {
                progress {
                    class: "download-progress",
                    value: progress.downloaded,
                    max: progress.total.unwrap_or(progress.downloaded.max(1)),
                }
                p { class: "notice", role: "status", "{mib:.1} МиБ" }
            }
            if !progress.error.is_empty() {
                p { class: "notice error-text", "{progress.error}" }
            }
            if *deleting.read() {
                div { role: "alert",
                    p {
                        "Удалить файл модели с устройства? Чаты сохранятся."
                    }
                    div { class: "row",
                        button {
                            class: "button",
                            onclick: move |_| deleting.set(false),
                            "Отмена"
                        }
                        button {
                            class: "button danger",
                            onclick: move |_| {
                                spawn(async move {
                                    let result = services::runtime::blocking(move || model_installer::remove(
                                            spec.id,
                                        ))
                                        .await;
                                    if result.is_ok() {
                                        deleting.set(false);
                                        if selected {
                                            state.write().model = String::new();
                                            if let Ok(store) = state::store(state) {
                                                let result = services::runtime::blocking(move || {
                                                        store
                                                            .with(|db| {
                                                                db.set_setting("chat_model", "")?;
                                                                Ok(())
                                                            })
                                                    })
                                                    .await;
                                                state::report(state, result);
                                            }
                                        }
                                    }
                                    state::report(state, result);
                                });
                            },
                            "Подтвердить удаление модели"
                        }
                    }
                }
            }
        }
    }
}
