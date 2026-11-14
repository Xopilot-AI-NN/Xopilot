// Описание: Раскрываемые карточки действий прямо между запросом и ответом в ленте.
use crate::{
    app::{
        shared::icons,
        state::{self, AppState, Screen},
    },
    services::task_history::{self, Action},
};
use dioxus::prelude::*;
#[component]
/// Показывает ход, результат и подробности каждого реального вызова инструмента.
pub fn build_action_cards(actions: Vec<Action>) -> Element {
    let state = use_context::<Signal<AppState>>();
    rsx! {
        div {
            class: "agent-actions",
            role: "log",
            "aria-label": "Действия агента",
            for action in actions {
                if action.tool == "thinking" {
                    details {
                        key: "{action.id}",
                        class: "reasoning-trace",
                        open: true,
                        "data-state": action.state.clone(),
                        summary {
                            icons::build_icon {name: "psychology"}
                            strong { {action.arguments["title"].as_str().unwrap_or("Размышление")} }
                            span {class:"notice", if action.state=="running" {"Выполняется"} else if action.state=="completed" {"Готово"} else if action.state=="failed" {"Ошибка"} else {"Прервано"}}
                        }
                        p { {action.output["result"].as_str().unwrap_or_default()} }
                    }
                } else {
                details {
                    key: "{action.id}",
                    class: "agent-action",
                    "data-state": action.state.clone(),
                    summary {
                        icons::build_icon {
                            name: if matches!(action.state.as_str(), "running" | "approval") { "hourglass_empty" } else if action.state == "completed" { "check" } else { "info_outline" },
                        }
                        span {
                            class: "action-heading",
                            strong {
                                {task_history::title(&action.tool)}
                            }
                            if let Some(agent)=action.arguments["_agent"].as_str() {
                                small {"{agent}"}
                            }
                            small {
                                {
                                    action
                                        .arguments["path"]
                                        .as_str()
                                        .or_else(|| action.arguments["query"].as_str())
                                        .unwrap_or_default()
                                }
                            }
                        }
                        span {
                            class: "action-state",
                            if action.state == "running" {
                                "Выполняется"
                            } else if action.state == "approval" {
                                "Нужно разрешение"
                            } else if action.state == "completed" {
                                "Готово"
                            } else if action.state == "interrupted" {
                                "Прервано"
                            } else {
                                "Не выполнено"
                            }
                        }
                        icons::build_icon {
                            name: "expand_more",
                        }
                    }
                    div {
                        class: "action-details",
                        if !action.arguments.is_null() {
                            pre {
                                {serde_json::to_string_pretty(&action.arguments).unwrap_or_default()}
                            }
                        }
                        if let Some(error) = action.output["error"].as_str() {
                            p {
                                class: "error-text",
                                "{error}"
                            }
                            if error.contains("Подключите папку") {
                                button {
                                    class: "button",
                                    onclick: move |_| state::navigate(state, Screen::Workspaces),
                                    "Подключить папку проекта"
                                }
                            }
                        } else if !action.output.is_null() {
                            pre {
                                {
                                    action
                                        .output["result"]
                                        .as_str()
                                        .map(str::to_owned)
                                        .unwrap_or_else(|| {
                                            serde_json::to_string_pretty(&action.output["result"])
                                                .unwrap_or_default()
                                        })
                                }
                            }
                        }
                        if action.seconds > 0.0 {
                            small {
                                class: "notice",
                                "{action.seconds:.1} с"
                            }
                        }
                    }
                }
                }
            }
        }
    }
}
