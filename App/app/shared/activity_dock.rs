// Описание: Уведомления и фактический прогресс расположены над строкой ввода.
use crate::{
    app::{
        shared::icons, state::AppState,
        tasks::task_messages,
    },
    services::{self, model_import, model_installer},
};
use dioxus::prelude::*;
#[component]
/// Собирает сообщения, загрузки и состояние агента в одном месте без перекрытия ввода.
pub fn build_activity_dock() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let mut downloads = use_signal(
        Vec::<(String, model_installer::Progress)>::new,
    );
    let mut imported = use_signal(model_import::progress);
    let mut compute = use_signal(services::compute::status);
    use_future(move || async move {
        loop {
            let next = model_installer::MODELS
                .iter()
                .map(|m| {
                    (
                        m.id.to_owned(),
                        model_installer::progress(m.id),
                    )
                })
                .collect::<Vec<_>>();
            if *downloads.peek() != next {
                for (id, progress) in &next {
                    if matches!(
                        progress.phase.as_str(),
                        "downloading" | "verifying"
                    ) && state
                        .peek()
                        .dismissed_downloads
                        .contains(id)
                    {
                        state
                            .write()
                            .dismissed_downloads
                            .remove(id);
                    }
                }
                downloads.set(next);
            }
            let next = model_import::progress();
            if *imported.peek() != next {
                imported.set(next);
            }
            let next = services::compute::status();
            if *compute.peek() != next {
                compute.set(next);
            }
            services::runtime::background(async {
                tokio::time::sleep(
                    std::time::Duration::from_millis(250),
                )
                .await
            })
            .await;
        }
    });
    let error = state.read().error.clone();
    let notice = state.read().notice.clone();
    let completed = state.read().task_completion.clone();
    let import = imported.read().clone();
    rsx! {
        div {
            class: "activity-dock",
            "aria-label": "Уведомления и прогресс",
            if let Some(error) = error {
                div {
                    class: "snackbar error activity-item",
                    role: "alert",
                    span {
                        "{error}"
                    }
                    button {
                        class: "plain-icon",
                        title: "Закрыть сообщение",
                        onclick: move |_| state.write().error = None,
                        icons::build_icon {
                            name: "close",
                        }
                    }
                }
            } else if let Some(notice) = notice {
                div {
                    class: "snackbar activity-item",
                    role: "status",
                    span {
                        "{notice}"
                    }
                    button {
                        class: "plain-icon",
                        title: "Закрыть сообщение",
                        onclick: move |_| state.write().notice = None,
                        icons::build_icon {
                            name: "close",
                        }
                    }
                }
            }
            for (id, progress) in downloads
                .read()
                .iter()
                .filter(|(id, p)| {
                    matches!(p.phase.as_str(), "downloading" | "verifying" | "paused" | "waiting")
                        || ((p.downloaded > 0 || p.phase == "error")
                            && !state.read().dismissed_downloads.contains(id))
                })
            {
                div {
                    class: "activity-item download-activity",
                    "data-state": progress.phase.clone(),
                    role: "status",
                    div {
                        class: "row",
                        strong {
                            {model_installer::model(id).map(|m| m.name).unwrap_or("Модель")}
                        }
                        span {
                            class: "spacer",
                        }
                        small {
                            if progress.phase == "installed" {
                                "Готово"
                            } else if progress.phase == "paused" {
                                "На паузе"
                            } else if progress.phase == "verifying" {
                                "Проверка файла"
                            } else if progress.phase == "waiting" {
                                "Ожидание сети · Android продолжит автоматически"
                            } else if progress.phase == "error" {
                                "Ошибка загрузки"
                            } else {
                                {super::progress::byte_progress(progress.downloaded,progress.total)}
                            }
                        }
                        if matches!(progress.phase.as_str(), "downloading" | "waiting") {
                            button {
                                class: "plain-icon",
                                title: if cfg!(target_os = "android") { "Отменить загрузку" } else { "Приостановить загрузку" },
                                onclick: {
                                    let id = id.clone();
                                    move |_| {
                                        if cfg!(target_os = "android") {
                                            crate::app::state::report(state, model_installer::cancel(&id));
                                        } else {
                                            model_installer::pause(&id);
                                        }
                                    }
                                },
                                icons::build_icon {
                                    name: "stop",
                                }
                            }
                        } else if !matches!(progress.phase.as_str(), "paused" | "verifying") {
                            button {
                                class: "plain-icon",
                                title: "Скрыть прогресс загрузки",
                                onclick: {
                                    let id = id.clone();
                                    move |_| {
                                        state.write().dismissed_downloads.insert(id.clone());
                                    }
                                },
                                icons::build_icon {
                                    name: "close",
                                }
                            }
                        }
                    }
                    super::progress::build_progress_bar {
                        value: progress.total.filter(|total|*total>0).map(|total|progress.downloaded as f64/total as f64),
                        label: "Загрузка модели",
                    }
                    if !progress.error.is_empty() {
                        p { class: "notice error-text", "{progress.error}" }
                    }
                }
            }
            if !import.phase.is_empty() && import.phase != "cancelled" {
                div {
                    class: "activity-item import-activity",
                    "data-state": import.phase.clone(),
                    role: "status",
                    div {
                        class: "row",
                        span {
                            "{import.message}"
                        }
                        span {
                            class: "spacer",
                        }
                        if !matches!(import.phase.as_str(), "copying" | "verifying") {
                            button {
                                class: "plain-icon",
                                title: "Скрыть результат импорта",
                                onclick: move |_| model_import::dismiss(),
                                icons::build_icon {
                                    name: "close",
                                }
                            }
                        }
                    }
                    small { class: "progress-caption", {super::progress::byte_progress(import.received,Some(import.total))} }
                    super::progress::build_progress_bar {
                        value: (import.total>0).then_some(import.received as f64/import.total.max(1) as f64),
                        label: "Импорт модели",
                    }
                }
            }
            if compute.read().loading {
                div {
                    class: "activity-item",
                    role: "status",
                    span {
                        "Загружаем модель · {compute.read().backend.to_uppercase()}"
                    }
                    super::progress::build_progress_bar {
                        value: None,
                        label: "Подготовка модели",
                    }
                }
            }
            task_messages::build_task_messages {
            }
            if let Some((message, success)) = completed {
                div {
                    class: "activity-item task-completion",
                    role: "status",
                    div {
                        class: "row",
                        icons::build_icon {
                            name: if success { "check" } else { "info_outline" },
                        }
                        span {
                            "{message}"
                        }
                        span {
                            class: "spacer",
                        }
                        button {
                            class: "plain-icon",
                            title: "Скрыть результат задачи",
                            onclick: move |_| state.write().task_completion = None,
                            icons::build_icon {
                                name: "close",
                            }
                        }
                    }
                    if success {
                        super::progress::build_progress_bar {
                            value: Some(1.0),
                            label: "Работа завершена",
                        }
                    }
                }
            }
        }
    }
}
