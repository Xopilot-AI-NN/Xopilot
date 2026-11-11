// Описание: Общая строка состояния задачи и сохранённый журнал действий агента.
use crate::app::state::AppState;
use dioxus::prelude::*;
#[component]
pub fn build_task_messages() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    rsx! {
        if state.read().busy && state.read().agent.enabled {
            div { class: "row agent-status", role: "status",
                span { class: "notice", "{state.read().agent_progress}" }
                if let Some(control) = state.read().agent_control.clone() {
                    button {
                        class: "button",
                        onclick: move |_| {
                            let paused = !control.paused();
                            control.set_paused(paused);
                            state.write().agent_progress = if paused {
                                "Задача на паузе; текущее действие завершится"
                                    .into()
                            } else {
                                "Продолжаю задачу".into()
                            };
                        },
                        if state.read().agent_control.as_ref().is_some_and(|c| c.paused()) {
                            "Продолжить"
                        } else {
                            "Пауза"
                        }
                    }
                }
            }
        }
        if !state.read().agent_log.is_empty() {
            details { class: "agent-trace",
                summary { "Действия агента · {state.read().agent_log.len()}" }
                pre { {state.read().agent_log.join("\n\n")} }
            }
        }
    }
}
