// Описание: Изолированный визуальный стенд. Не открывает пользовательскую базу и сеть.
// dx build --desktop -p xopilot --example interface_preview
// Бинарник принимает: empty, messages, drawer, settings, personalization, api, mobile.
use advanced_xopilot::db::Database;
use dioxus::prelude::*;
use xopilot::{
    app::{
        main::build_window,
        state::{AppState, Screen},
    },
    services::{chat_store, db::Store},
};

/// Запускает отдельный проверочный стенд без обращения к личной истории.
fn main() {
    let mobile = std::env::args().any(|s| s.starts_with("mobile"));
    dioxus::LaunchBuilder::desktop()
        .with_cfg(
            dioxus::desktop::Config::new().with_menu(None).with_window(
                dioxus::desktop::WindowBuilder::new()
                    .with_title("Xopilot · UI preview")
                    .with_inner_size(dioxus::desktop::LogicalSize::new(
                        if mobile { 390.0 } else { 1000.0 },
                        720.0,
                    ))
                    .with_min_inner_size(dioxus::desktop::LogicalSize::new(320.0, 260.0)),
            ),
        )
        .launch(preview);
}

/// Собирает изолированное состояние интерфейса для проверки.
#[component]
fn preview() -> Element {
    let scenario = use_hook(|| std::env::args().nth(1).unwrap_or_else(|| "empty".into()));
    let scenario_for_state = scenario.clone();
    let _state = use_context_provider(move || {
        let store = Store::new(Database::open(":memory:", &"a".repeat(64)).unwrap());
        let snapshot = store.with(|db| {
            let id = db.create_chat(if scenario_for_state == "messages" { "Знакомство с Xopilot" } else { "Новый чат" })?;
            if scenario_for_state == "messages" {
                db.add_message_full(id, "user", "Привет! Что ты умеешь?", None, None, &[], None)?;
                db.add_message_full(id, "ai", "**Zephyr**\n\nПриветствую! Я ваш ассистент в Xopilot.\n\nЧем я могу быть полезен сегодня? У вас есть конкретный вопрос, задача или тема, которую вы хотели бы обсудить?", None, None, &[], Some(1.4))?;
            }
            chat_store::load(db, Some(id))
        }).unwrap();
        let mut state = AppState {
            store: Some(store),
            ready: true,
            ..Default::default()
        };
        state.apply(snapshot);
        state.screen = match scenario_for_state.as_str() {
            "settings" | "personalization" | "mobile-settings" => Screen::Settings,
            "api" => Screen::Api,
            "models" => Screen::Model,
            "projects" => Screen::Workspaces,
            "canvas" => Screen::Canvas,
            "templates" => Screen::Templates,
            "chats" => Screen::Chats,
            _ => Screen::Chat,
        };
        state.sidebar = scenario_for_state.ends_with("drawer");
        if scenario_for_state == "dark" {
            state.theme = "dark".into();
        }
        Signal::new(state)
    });
    use_future(move || {
        let scenario = scenario.clone();
        async move {
            xopilot::services::runtime::background(async {
                tokio::time::sleep(std::time::Duration::from_millis(1000)).await
            })
            .await;
            if scenario == "personalization" {
                document::eval(
                    "document.querySelectorAll('.settings-navigation-row')[1]?.click();",
                );
                xopilot::services::runtime::background(async {
                    tokio::time::sleep(std::time::Duration::from_millis(350)).await
                })
                .await;
            }
            let metrics = document::eval(r#"
            await document.fonts.ready;
            const rect = selector => {
                const el = document.querySelector(selector);
                if (!el) return null;
                const r=el.getBoundingClientRect(), s=getComputedStyle(el);
                return {x:r.x,y:r.y,width:r.width,height:r.height,font:s.fontSize,background:s.backgroundColor,radius:s.borderRadius,display:s.display};
            };
            return {viewport:[innerWidth,innerHeight],rail:rect('.navigation-rail'),header:rect('.chat-header'),main:rect('.main'),composer:rect('.composer'),title:rect('.empty h1'),drawer:rect('.drawer'),dialog:rect('.dialog'),materialIcons:document.fonts.check('20px MaterialIcons'),horizontalOverflow:document.documentElement.scrollWidth>innerWidth};
        "#).await;
            match metrics {
                Ok(value) => println!("UI_QA {value}"),
                Err(error) => eprintln!("UI_QA_ERROR {error}"),
            };
        }
    });
    rsx! {
        build_window {

        }
    }
}
