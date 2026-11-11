// Описание: Установленная версия, изменения сборки и настоящий ответ проверки релизов.
use crate::{
    app::{
        shared::icons,
        state::{self, AppState},
    },
    services,
};
use dioxus::prelude::*;
/// Показывает изменения сборки и результат ручной проверки релиза.
#[component]
pub fn build_updates() -> Element {
    let state = use_context::<Signal<AppState>>();
    let mut busy = use_signal(|| false);
    let mut status = use_signal(String::new);
    let mut release = use_signal(|| None::<services::updates::Release>);
    rsx! {
        div {
            class: "updates-page",
            section {
                class: "update-installed",
                span {
                    class: "preference-icon tone-navigate",
                    icons::build_icon {
                        name: "system_update_outlined",
                    }
                }
                div {
                    class: "catalog-copy",
                    strong {
                        {concat!("Xopilot ", env!("CARGO_PKG_VERSION"))}
                    }
                    small {
                        "Установлено · Rust / Dioxus"
                    }
                }
                button {
                    class: "button",
                    disabled: *busy.read(),
                    onclick: move |_| {
                        busy.set(true);
                        status.set("Проверяем GitHub…".into());
                        spawn(async move {
                            match services::runtime::background(services::updates::latest()).await {
                                Ok(Some(found)) => {
                                    status
                                        .set(
                                            if found.version.trim_start_matches('v')
                                                == env!("CARGO_PKG_VERSION")
                                            {
                                                "Установлена последняя опубликованная версия"
                                                    .into()
                                            } else {
                                                format!(
                                                    "Доступен релиз {}. Сравните его с установленной версией.",
                                                    found.version,
                                                )
                                            },
                                        );
                                    release.set(Some(found));
                                }
                                Ok(None) => {
                                    status
                                        .set(
                                            "Опубликованных стабильных релизов пока нет"
                                                .into(),
                                        )
                                }
                                Err(e) => status.set(e.to_string()),
                            }
                            busy.set(false);
                        });
                    },
                    if *busy.read() {
                        "Проверяем…"
                    } else {
                        "Проверить обновления"
                    }
                }
            }
            if !status.read().is_empty() {
                p {
                    class: "notice",
                    role: "status",
                    "{status}"
                }
            }
            if let Some(found) = release.read().as_ref() {
                section {
                    class: "release-notes",
                    h2 {
                        "{found.version}"
                    }
                    div {
                        class: "markdown",
                        dangerous_inner_html: crate::app::chat::messages::message::markdown_html(&found.notes),
                    }
                    button {
                        class: "button",
                        onclick: {
                            let url = found.url.clone();
                            move |_| state::report(state, services::platform_links::open(&url))
                        },
                        "Открыть релиз"
                    }
                }
            }
            h2 {
                class: "section-title",
                "Что нового в этой сборке"
            }
            for (icon, title, description) in [
                (
                    "smart_toy_outlined",
                    "Модели на устройстве",
                    "Загрузка и импорт Gemma, проверка целостности и работа без API.",
                ),
                (
                    "fact_check_outlined",
                    "Агент для проектов",
                    "Чтение и изменение файлов, подтверждение действий, пауза и журнал.",
                ),
                (
                    "person_outline",
                    "Профиль и аккаунты",
                    "Редактирование имени и аватара, отдельные локальные профили.",
                ),
                (
                    "palette_outlined",
                    "Знакомый интерфейс",
                    "Семь тем, компактные карточки и списки в цветах приложения.",
                ),
            ]
            {
                section {
                    class: "update-change",
                    icons::build_icon {
                        name: icon,
                    }
                    div {
                        strong {
                            "{title}"
                        }
                        p {
                            class: "notice",
                            "{description}"
                        }
                    }
                }
            }
            p {
                class: "notice",
                "Проверка обращается к GitHub. Установка выполняется вручную из опубликованного пакета; переписка не передаётся."
            }
        }
    }
}
