// Описание: Режим инструментов меняется явно; автоподтверждение не включается само.
use crate::{
    app::{
        shared::{icons, popover},
        state::{self, AppState},
    },
    services,
};
use dioxus::prelude::*;
/// Меняет режим агента только по явному решению пользователя.
#[component]
pub fn build_agent_controls() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let mut open = use_signal(|| false);
    let settings = state.read().agent.clone();
    let label = if !settings.enabled {
        "Чат"
    } else if settings.automatic {
        "Авто"
    } else {
        "Вручную"
    };
    rsx! {
        button {
            id: "agent-mode-trigger",
            class: "confirmation-button",
            title: "Режим агента",
            "aria-label": "Режим агента",
            "aria-expanded": *open.read(),
            disabled: state.read().busy,
            onclick: move |_| {
                let next = !*open.peek();
                open.set(next);
            },
            icons::build_icon {
                name: "fact_check_outlined",
            }
            span {
                "{label}"
            }
        }
        if *open.read() {
            popover::build_popover {
                id: "agent-mode-menu",
                anchor: "agent-mode-trigger",
                onclose: move |_| open.set(false),
                for (label, enabled, automatic) in [
                    ("Чат без инструментов", false, false),
                    ("Агент · подтверждать действия", true, false),
                    ("Агент · автоматически", true, true),
                ]
                {
                    button {
                        class: "popup-item",
                        onclick: move |_| {
                            let settings = services::agent::Settings {
                                enabled,
                                automatic,
                                ..Default::default()
                            };
                            spawn(async move {
                                let result = async {
                                    let store = state::store(state)?;
                                    let chat = state
                                        .peek()
                                        .active
                                        .ok_or_else(|| anyhow::anyhow!("Чат не выбран"))?;
                                    let saved = settings.clone();
                                    services::runtime::blocking(move || services::agent::save_settings(
                                            &store,
                                            chat,
                                            &saved,
                                        ))
                                        .await?;
                                    state.write().agent = settings;
                                    open.set(false);
                                    Ok(())
                                }
                                    .await;
                                state::report(state, result);
                            });
                        },
                        "{label}"
                    }
                }
                p {
                    class: "notice popover-description",
                    "Авто разрешает агенту изменять файлы выбранного проекта и запускать команды без отдельного вопроса. Сохранение личной памяти подтверждается всегда."
                }
            }
        }
    }
}
