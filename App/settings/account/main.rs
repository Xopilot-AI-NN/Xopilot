// Описание: Профиль и вход собраны в одну страницу, по прежней архитектуре account/.
use crate::{
    app::{
        shared::icons,
        state::{self, AppState},
    },
    services::{self, profiles::Usage},
};
use dioxus::prelude::*;
/// Объединяет автоматически созданный профиль, редактирование и серверный вход.
#[component]
pub fn build_account_page() -> Element {
    let state = use_context::<Signal<AppState>>();
    let mut name =
        use_signal(|| "Пользователь".to_string());
    let mut avatar = use_signal(String::new);
    let mut draft = use_signal(String::new);
    let mut editing = use_signal(|| false);
    let mut dirty = use_signal(|| false);
    let mut usage = use_signal(Usage::default);
    let mut revision = use_signal(|| 0u64);
    crate::app::shared::unsaved::use_unsaved(dirty);
    let _load = use_resource(move || {
        let _revision = *revision.read();
        async move {
            let result = async {
                let store = state::store(state)?;
                let root = services::paths::app_data_dir()?;
                let (profile, stats) =
                    services::runtime::blocking(
                        move || {
                            Ok((
                                services::profile::read(
                                    &store,
                                )?,
                                services::profiles::usage(
                                    &store, &root,
                                )?,
                            ))
                        },
                    )
                    .await?;
                name.set(
                    profile["name"]
                        .as_str()
                        .unwrap_or("Пользователь")
                        .into(),
                );
                avatar.set(
                    profile["avatar"]
                        .as_str()
                        .unwrap_or_default()
                        .into(),
                );
                usage.set(stats);
                Ok(())
            }
            .await;
            state::report(state, result);
        }
    });
    let mib = usage.read().bytes as f64 / 1048576.0;
    rsx! {
        div {
            class: "account-page",
            section {
                class: "profile-identity",
                super::avatar::build_avatar {
                    value: avatar.read().clone(),
                    onchange: move |value| avatar.set(value),
                }
                div {
                    class: "profile-identity-copy",

                    if *editing.read() {
                        form {
                            class: "profile-name-inline-editor",

                            onsubmit: move |e| {
                                e.prevent_default();

                                let requested = draft.peek().trim().to_owned();
                                if requested.is_empty() {
                                    return;
                                }

                                spawn(async move {
                                    let result = async {
                                        let store = state::store(state)?;
                                        let value = requested.clone();

                                        services::runtime::blocking(move || {
                                            services::profile::rename(&store, &value)
                                        })
                                        .await?;

                                        name.set(requested);
                                        editing.set(false);
                                        dirty.set(false);
                                        Ok(())
                                    }
                                    .await;

                                    state::report(state, result);
                                });
                            },

                            input {
                                class: "profile-name-input",
                                value: "{draft}",
                                maxlength: 50,
                                autofocus: true,

                                oninput: move |e| {
                                    draft.set(e.value());
                                    dirty.set(true);
                                },

                                onkeydown: move |e| {
                                    if e.key() == Key::Escape {
                                        editing.set(false);
                                        dirty.set(false);
                                    }
                                },
                            }

                            button {
                                r#type: "submit",
                                class: "profile-name-action",
                                title: "Сохранить имя",
                                "✓"
                            }

                            button {
                                r#type: "button",
                                class: "profile-name-action",
                                title: "Отмена",
                                onclick: move |_| {
                                    editing.set(false);
                                    dirty.set(false);
                                },
                                "×"
                            }
                        }
                    } else {
                        button {
                            class: "profile-name",
                            title: "Изменить имя",
                            onclick: move |_| {
                                draft.set(name.peek().clone());
                                editing.set(true);
                            },

                            span { "{name}" }

                            icons::build_icon {
                                name: "edit",
                            }
                        }
                    }

                    p {
                        class: "notice",
                        "Профиль создан автоматически на этом устройстве"
                    }
                }
            }
            super::cloud::build_cloud_card {
                onchange: move |_| revision += 1,
            }
            h2 {
                class: "section-title",
                "Статистика использования"
            }
            div {
                class: "profile-statistics",
                for (icon, label, value) in [
                    ("forum_outlined", "Чаты", usage.read().chats.to_string()),
                    ("chat_bubble_outline", "Сообщения", usage.read().messages.to_string()),
                    ("storage", "Данные", format!("{mib:.1} МиБ")),
                ]
                {
                    div {
                        class: "profile-stat",
                        icons::build_icon {
                            name: icon,
                        }
                        small {
                            "{label}"
                        }
                        strong {
                            "{value}"
                        }
                    }
                }
            }

        }
    }
}
