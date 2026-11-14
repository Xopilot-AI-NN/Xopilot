// Добавил новые агентности. Режим команды и разрешение менять файлы выбираются отдельно.
use crate::{
    app::{
        shared::{icons, popover},
        state::{self, AppState},
    },
    services::{
        self,
        agent::Settings,
        agent_modes::{Depth, Mode},
    },
};
use dioxus::prelude::*;

/// Сохраняю настройки выбранного чата, текущая задача сохраняет прежние разрешения.
async fn save(
    mut state: Signal<AppState>,
    settings: Settings,
) -> anyhow::Result<()> {
    let store = state::store(state)?;
    let chat = state
        .read()
        .active
        .ok_or_else(|| anyhow::anyhow!("Чат не выбран"))?;
    let saved = settings.clone();
    services::runtime::blocking(move || {
        services::agent::save_settings(&store, chat, &saved)
    })
    .await?;
    state.write().agent = settings;
    if state.read().busy {
        state.write().notice = Some(
            "Режим изменён для следующей задачи".into(),
        );
    }
    Ok(())
}

/// Изменение настроек выполняется одним обработчиком для всех кнопок.
fn apply(state: Signal<AppState>, settings: Settings) {
    spawn(async move {
        let result = save(state, settings).await;
        state::report(state, result);
    });
}
/// Выбор команды не сбрасывает глубину размышления.
fn select_mode(
    state: Signal<AppState>,
    mut open: Signal<bool>,
    enabled: bool,
    automatic: bool,
    mode: Mode,
) {
    let selected = Settings {
        enabled,
        automatic,
        mode,
        ..state.read().agent.clone()
    };
    open.set(false);
    apply(state, selected);
}
/// Автоматическое разрешение отделено от количества исследователей.
fn toggle_automatic(state: Signal<AppState>) {
    let mut selected = state.read().agent.clone();
    selected.automatic = !selected.automatic;
    apply(state, selected);
}
/// Краткий план можно отдельно включать для обычного чата.
fn toggle_reasoning(
    state: Signal<AppState>,
    enabled: bool,
) {
    let mut selected = state.read().agent.clone();
    selected.reasoning = !enabled;
    apply(state, selected);
}
/// Изменение уровня применяется к следующей задаче.
fn select_depth(
    state: Signal<AppState>,
    mut open: Signal<bool>,
    depth: Depth,
) {
    let mut selected = state.read().agent.clone();
    selected.depth = depth;
    selected.reasoning = true;
    open.set(false);
    apply(state, selected);
}

/// Показываю все агентности в прежнем тематическом списке.
#[component]
pub fn build_agent_controls() -> Element {
    let state = use_context::<Signal<AppState>>();
    let mut open = use_signal(|| false);
    let settings = state.read().agent.clone();
    let label = if !settings.enabled {
        "Чат"
    } else if settings.mode != Mode::Standard {
        settings.mode.label()
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
            onclick: move |_| { let next=!*open.peek(); open.set(next); },
            icons::build_icon { name: "fact_check_outlined" }
            span { class: "agent-mode-label", "{label}" }
        }
        if *open.read() {
            popover::build_popover {
                id: "agent-mode-menu",
                anchor: "agent-mode-trigger",
                onclose: move |_|open.set(false),
                for (label,enabled,automatic,mode) in [
                    ("Чат без инструментов",false,false,Mode::Standard),
                    ("Агент · подтверждать действия",true,false,Mode::Standard),
                    ("Агент · автоматически",true,true,Mode::Standard),
                    ("Точный агент",true,settings.automatic,Mode::Precise),
                    ("Мульти Агенты",true,settings.automatic,Mode::Multi),
                    ("Мульти Агенты с подкреплением",true,settings.automatic,Mode::Reinforced),
                ] {
                    button {
                        class: "popup-item",
                        "aria-pressed": settings.enabled==enabled && settings.automatic==automatic && settings.mode==mode,
                        onclick: move |_| select_mode(state,open,enabled,automatic,mode),
                        "{label}"
                    }
                }
                if settings.mode!=Mode::Standard {
                    button {
                        class: "popup-item",
                        onclick: move |_| toggle_automatic(state),
                        if settings.automatic {"Переключить на подтверждение действий"} else {"Разрешить действия автоматически"}
                    }
                }
                p { class: "notice popover-description", "Пять исследователей читают и проверяют данные. Изменения выполняет основной агент с выбранными разрешениями. Локальная модель обслуживает исследования по очереди; API допускает параллельные запросы. Авто разрешает запись и команды проекта, память подтверждается всегда." }
            }
        }
        build_reasoning_controls {}
    }
}

/// Вынес глубину в отдельную кнопку, уровни соответствуют одному–четырём проходам.
#[component]
fn build_reasoning_controls() -> Element {
    let state = use_context::<Signal<AppState>>();
    let mut open = use_signal(|| false);
    let settings = state.read().agent.clone();
    let forced = matches!(
        settings.mode,
        Mode::Precise | Mode::Reinforced
    ) && settings.enabled;
    let enabled = settings.reasoning || forced;
    let label = if enabled {
        settings.depth.label()
    } else {
        "Выкл"
    };
    rsx! {
        button {
            id: "reasoning-trigger",
            class: "confirmation-button reasoning-control",
            title: "Размышление",
            "aria-label": "Размышление",
            "aria-expanded": *open.read(),
            onclick: move |_| {let next=!*open.peek();open.set(next);},
            icons::build_icon {name:"psychology"}
            span {class:"reasoning-depth-label", "{label}"}
        }
        if *open.read() {
            popover::build_popover {
                id: "reasoning-menu",
                anchor: "reasoning-trigger",
                onclose: move |_| open.set(false),
                button {
                    class:"popup-item",
                    disabled:forced,
                    onclick: move |_| toggle_reasoning(state,enabled),
                    if enabled {"Выключить размышление"} else {"Включить размышление"}
                }
                for depth in [Depth::Light,Depth::Medium,Depth::High,Depth::Maximum] {
                    button {
                        class: "popup-item",
                        "aria-pressed": settings.depth==depth && enabled,
                        onclick: move |_| select_depth(state,open,depth),
                        {depth.label()}
                    }
                }
                p {class:"notice popover-description", "Глубина задаёт 1–4 дополнительных прохода модели: краткий план и проверку. Они видны в чате и увеличивают время ответа. Точный режим и координатор включают их обязательно."}
            }
        }
    }
}
