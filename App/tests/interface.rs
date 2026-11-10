use advanced_xopilot::db::Database;
use dioxus::prelude::*;
use xopilot::app::{self, state::AppState};
use xopilot::services::{chat_store, db::Store};

fn build_fixture() -> Element {
    let _state = use_context_provider(|| {
        let store = Store::new(Database::open(":memory:", &"a".repeat(64)).unwrap());
        let snapshot = store
            .with(|db| {
                let id = db.create_chat("Проверка интерфейса")?;
                db.add_message_full(id, "user", "Сообщение пользователя", None, None, &[], None)?;
                db.add_message_full(
                    id,
                    "ai",
                    "**Настоящий Markdown**",
                    None,
                    None,
                    &[],
                    Some(0.5),
                )?;
                chat_store::load(db, Some(id))
            })
            .unwrap();
        let mut state = AppState {
            store: Some(store),
            ready: true,
            model: "model-test".into(),
            ..Default::default()
        };
        state.apply(snapshot);
        Signal::new(state)
    });
    rsx! {
        app::menu::menu::build_menu {}
        app::chat::chat::build_chat {}
        xopilot::settings::main::build_settings_dialog {}
        app::settings::api_settings::build_api_settings {}
        xopilot::settings::personalizations::main::build_personalizations { account: true }
        app::canvas::canvas_editor::build_canvas_dialog {}
        app::workspace::workspace_browser::build_workspaces_dialog {}
        app::chat::composer::prompt_templates::build_templates {}
    }
}

#[test]
fn all_migrated_screens_render_with_real_store_context() {
    let mut dom = VirtualDom::new(build_fixture);
    dom.rebuild_in_place();
    let html = dioxus_ssr::render(&dom);
    for text in [
        "Проверка интерфейса",
        "Сообщение пользователя",
        "<strong>Настоящий Markdown</strong>",
        "Сохранить модель",
        "Сохранить профиль",
        "Новое пространство",
        "Сохранить",
        "Поиск шаблонов",
        "model-test",
    ] {
        assert!(html.contains(text), "Missing: {text}");
    }
    assert!(html.contains("type=\"file\""));
    assert!(html.contains("type=\"password\""));
}

fn window_fixture() -> Element {
    let _state = use_context_provider(|| {
        let store = Store::new(Database::open(":memory:", &"a".repeat(64)).unwrap());
        let snapshot = store.with(|db| chat_store::load(db, None)).unwrap();
        let mut state = AppState {
            store: Some(store),
            ready: true,
            screen: app::state::Screen::Settings,
            ..Default::default()
        };
        state.apply(snapshot);
        Signal::new(state)
    });
    rsx! { app::main::build_window {} }
}

#[test]
fn settings_overlay_retains_chat_and_exposes_original_sections() {
    let mut dom = VirtualDom::new(window_fixture);
    dom.rebuild_in_place();
    let html = dioxus_ssr::render(&dom);
    assert!(html.contains("role=\"dialog\""));
    assert!(
        html.contains("id=\"chat-prompt\""),
        "Chat must remain mounted behind settings"
    );
    for label in [
        "Параметры приложения",
        "Профиль и аккаунт",
        "Персонализация",
        "Модели",
        "История",
        "Обновления",
        "О программе",
    ] {
        assert!(html.contains(label), "Missing original section: {label}");
    }
    assert!(!html.contains("История хранится локально в SQLCipher."));
    assert!(!html.contains("Твой ИИ. Твои проекты."));
}

fn open_drawer_fixture() -> Element {
    let _state = use_context_provider(|| {
        Signal::new(AppState {
            sidebar: true,
            ..Default::default()
        })
    });
    rsx! { app::menu::menu::build_menu_overlay {} }
}

#[test]
fn open_drawer_removes_inert_instead_of_setting_it_to_false() {
    let mut dom = VirtualDom::new(open_drawer_fixture);
    dom.rebuild_in_place();
    let html = dioxus_ssr::render(&dom);
    assert!(html.contains("drawer-layer open"));
    assert!(
        !html.contains("inert="),
        "Любое значение HTML inert блокирует меню"
    );
    assert!(html.contains("aria-modal=\"true\""));
}
