// Файл: App/app/main.rs
// Разработчик: DenBroLiik
// Описание: Окно собирается из меню, чата, строки ввода и страниц настроек.
use super::{
    chat, menu,
    state::{self, AppState},
    theme::palette,
};
use crate::{
    app::{dialogs, shared::icons},
    services,
};
use dioxus::prelude::*;

const FONT: Asset = asset!("/assets/fonts/GoogleSans-Regular.ttf");

#[component]
pub fn build_app_ui() -> Element {
    let state = use_context_provider(|| {
        Signal::new(AppState {
            theme: "light".into(),
            ..Default::default()
        })
    });
    use_future(move || async move {
        state::initialize(state).await;
    });
    let draft_revision = use_hook(|| std::sync::Arc::new(std::sync::atomic::AtomicU64::new(0)));
    let draft_to_save = use_memo(move || {
        let value = state.read();
        (value.session_revision, value.active, value.draft.clone())
    });
    // Отменяем ожидание предыдущего черновика, когда пользователь продолжает ввод.
    let _draft_writer = use_resource(move || {
        use std::sync::atomic::Ordering;
        let revision = draft_revision.fetch_add(1, Ordering::SeqCst) + 1;
        let current_revision = draft_revision.clone();
        let (_session, active, draft) = draft_to_save.read().clone();
        let store = state.peek().store.clone();
        async move {
            if let (Some(store), Some(id)) = (store, active) {
                let result = services::runtime::background(async move {
                    tokio::time::sleep(std::time::Duration::from_millis(400)).await;
                    store
                        .run(move |db| {
                            if current_revision.load(Ordering::SeqCst) == revision {
                                services::drafts::write_draft(db, id, &draft)?;
                            }
                            Ok(())
                        })
                        .await
                })
                .await;
                state::report(state, result);
            }
        }
    });
    rsx! { self::build_window { key:"{state.read().session_revision}" } }
}

/// Компоновка отдельно от инициализации: её можно проверить на тестовой базе.
#[component]
pub fn build_window() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let value = state.read();
    let theme = value.theme.clone();
    let ready = value.ready;
    let has_store = value.store.is_some();
    let error = value.error.clone();
    let notice = value.notice.clone();
    let pending_screen = value.pending_screen;
    let pending_section = value.pending_section;
    let approval = value.approval.clone();
    let approval_open = approval.is_some();
    drop(value);
    // Обычное уведомление не должно навсегда перекрывать кнопки на телефоне.
    let notice_value = use_memo(move || state.read().notice.clone());
    let _notice_timeout = use_resource(move || {
        let notice = notice_value.read().clone();
        async move {
            if notice.is_some() {
                services::runtime::background(async {
                    tokio::time::sleep(std::time::Duration::from_secs(5)).await;
                })
                .await;
                if state.peek().notice == notice {
                    state.write().notice = None;
                }
            }
        }
    });
    use_effect(use_reactive(
        (&pending_screen, &pending_section, &approval_open),
        move |(screen, section, approval)| {
            if screen.is_some() || section.is_some() || approval {
                document::eval(include_str!("shared/dialog_focus.js"));
            }
        },
    ));
    rsx! {
        style { {format!("@font-face{{font-family:GoogleSans;src:url('{FONT}')}}@font-face{{font-family:MaterialIcons;src:url('{}')}}{}", icons::FONT, palette::STYLES)} }
        document::Link { rel: "icon", href: asset!("/assets/icon.png") }
        div { class: "app", "data-theme": theme, "data-platform": if cfg!(target_os = "android") { "android" } else { "desktop" },
            if !ready {
                div { class: "empty", role: "status", "Открываем защищённую историю…" }
            } else if !has_store {
                div { class: "empty",
                    icons::build_icon { name: "lock_outline" }
                    h1 { "История недоступна" }
                    p { "Проверьте системное хранилище ключей. Данные не перезаписывались." }
                    button { class: "button", onclick: move |_| { state.write().ready = false; spawn(async move { state::initialize(state).await; }); }, "Повторить" }
                }
            } else {
                div { class: "layout",
                    menu::menu::build_menu {}
                    main { class: "main", chat::chat::build_chat {} }
                    menu::menu::build_menu_overlay {}
                }
                dialogs::build_overlay {}
            }
            if let Some(error) = error {
                div { class: "snackbar error", role: "alert",
                    span { "{error}" }
                    button { class: "plain-icon", title: "Закрыть сообщение", onclick: move |_| state.write().error = None, icons::build_icon { name: "close" } }
                }
            } else if let Some(notice) = notice {
                div { class: "snackbar", role: "status",
                    span { "{notice}" }
                    button { class: "plain-icon", title: "Закрыть сообщение", onclick: move |_| state.write().notice = None, icons::build_icon { name: "close" } }
                }
            }
            if pending_screen.is_some() || pending_section.is_some() {
                div { class: "modal-backdrop confirmation-backdrop",
                    section { class: "confirmation", role: "alertdialog", "aria-modal": "true", "aria-label": "Несохранённые изменения", tabindex: -1,
                        onkeydown: move |event| { if event.key() == Key::Escape { event.stop_propagation(); state.write().pending_screen = None; state.write().pending_section = None; } },
                        h2 { "Отбросить изменения?" }
                        p { "В форме есть несохранённые изменения." }
                        div { class: "row dialog-actions",
                            button { class: "button", onclick: move |_| { state.write().pending_screen = None; state.write().pending_section = None; document::eval(include_str!("shared/dialog_focus.js")); }, "Остаться" }
                            button { class: "button danger", onclick: move |_| state::discard_pending(state), "Отбросить и перейти" }
                        }
                    }
                }
            }
            if let Some(approval)=approval{
                div{class:"modal-backdrop confirmation-backdrop",
                    section{class:"confirmation agent-approval",role:"alertdialog","aria-modal":"true","aria-label":"Подтверждение действия агента",tabindex:-1,
                        onkeydown:{let approval=approval.clone();move|event:KeyboardEvent|{if event.key()==Key::Escape{event.stop_propagation();approval.answer(false);state.write().approval=None;}}},
                        h2{"{approval.title}"}
                        pre{class:"approval-details","{approval.details}"}
                        div{class:"row dialog-actions",
                            button{class:"button",onclick:{let approval=approval.clone();move|_|{approval.answer(false);state.write().approval=None;}},"Отклонить"}
                            button{class:"button primary",onclick:move|_|{approval.answer(true);state.write().approval=None;},"Разрешить действие"}
                            button{class:"button danger",onclick:move|_|{state::cancel(state);state.write().approval=None;},"Остановить задачу"}
                        }
                    }
                }
            }
        }
    }
}
