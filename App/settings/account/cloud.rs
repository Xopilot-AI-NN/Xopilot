// Описание: Google и почта используют серверный контракт; локальные профили находятся отдельно.
use crate::{
    app::state::{self, AppState},
    services::{self, cloud_account as cloud},
};
use dioxus::prelude::*;
use tokio_util::sync::CancellationToken;
use zeroize::Zeroizing;

/// Показывает Google и почту; сетевые запросы выполняются только по нажатию.
#[component]
pub fn build_cloud_card(
    onchange: EventHandler<()>,
) -> Element {
    let state = use_context::<Signal<AppState>>();
    let mut mode = use_signal(|| "".to_string());
    let mut email = use_signal(String::new);
    let mut username = use_signal(String::new);
    let mut password = use_signal(String::new);
    let mut repeat = use_signal(String::new);
    let mut code = use_signal(String::new);
    let mut registration = use_signal(String::new);
    let mut busy = use_signal(|| false);
    let mut message = use_signal(String::new);
    let mut session = use_signal(|| {
        state::store(state)
            .ok()
            .and_then(|s| cloud::state(&s).ok().flatten())
    });
    let cancellation = use_hook(CancellationToken::new);
    let cleanup = cancellation.clone();
    use_drop(move || cleanup.cancel());
    let google_cancel = cancellation.clone();
    let submit_cancel = cancellation.clone();
    rsx! {
        section {
            class: "cloud-account-card",
            if let Some(account) = session.read().as_ref() {
                h2 {
                    "Аккаунт Xopilot"
                }
                p {
                    {account["email"].as_str().unwrap_or_default()}
                }
                p {
                    class: "notice",
                    "Вход сохранён на этом устройстве. Синхронизация пока недоступна."
                }
                button {
                    class: "button",
                    onclick: move |_| {
                        let result = state::store(state).and_then(|s| cloud::forget(&s));
                        if result.is_ok() {
                            session.set(None);
                            onchange.call(());
                        }
                        state::report(state, result);
                    },
                    "Выйти на этом устройстве"
                }
            } else {
                h2 {
                    "Аккаунт Xopilot"
                }
                p {
                    class: "notice",
                    "Войдите для подключения аккаунта. Для работы без сервера вход не требуется."
                }
                div {
                    class: "account-auth-actions",
                    button {
                        class: "button google-signin",
                        disabled: *busy.read(),
                        onclick: move |_| {
                            busy.set(true);
                            message.set("Открываем Google…".into());
                            let cancelled = google_cancel.clone();
                            spawn(async move {
                                let result: anyhow::Result<()> = async {
                                    let store = state::store(state)?;
                                    let flow = cloud::begin_google(&store).await?;
                                    if cancelled.is_cancelled() {
                                        cloud::cancel_google(&flow).await;
                                        anyhow::bail!("Вход отменён");
                                    }
                                    let opened = services::platform_links::open(&flow.browser_url);
                                    if let Err(error) = opened {
                                        cloud::cancel_google(&flow).await;
                                        return Err(error);
                                    }
                                    message
                                        .set(
                                            "Завершите вход в браузере. Ожидаем подтверждения…"
                                                .into(),
                                        );
                                    let outcome = async {
                                        for _ in 0..120 {
                                            tokio::select! {
                                                _ = cancelled.cancelled() =>
                                                anyhow::bail!("Вход отменён"), _ =
                                                services::runtime::background(async {
                                                tokio::time::sleep(std::time::Duration::from_secs(2)). await
                                                }) => {}
                                            }
                                            if cloud::poll_google(&store, &flow, &cancelled).await? {
                                                return Ok(());
                                            }
                                        }
                                        anyhow::bail!(
                                            "Время входа истекло. Повторите попытку"
                                        )
                                    }
                                        .await;
                                    if outcome.is_err() {
                                        cloud::cancel_google(&flow).await;
                                    }
                                    outcome?;
                                    session.set(cloud::state(&store)?);
                                    onchange.call(());
                                    Ok(())
                                }
                                    .await;
                                busy.set(false);
                                message
                                    .set(
                                        match result {
                                            Ok(()) => "Вход выполнен".into(),
                                            Err(error) => error.to_string(),
                                        },
                                    );
                            });
                        },
                        span {
                            class: "google-letter",
                            "G"
                        }
                        "Продолжить с Google"
                    }
                    button {
                        class: "button",
                        style: "margin-left: auto;",
                        disabled: *busy.read(),
                        onclick: move |_| {
                            mode.set("login".into());
                            message.set(String::new());
                        },
                        "Войти по почте"
                    }
                    button {
                        class: "button",
                        disabled: *busy.read(),
                        onclick: move |_| {
                            mode.set("register".into());
                            message.set(String::new());
                        },
                        "Регистрация"
                    }
                }
                if !mode.read().is_empty() {
                    form {
                        class: "account-auth-form",
                        onsubmit: move |event| {
                            event.prevent_default();
                            if *busy.peek() {
                                return;
                            }
                            busy.set(true);
                            message.set(String::new());
                            let selected = mode.peek().clone();
                            let address = email.peek().clone();
                            let name = username.peek().clone();
                            let secret = Zeroizing::new(password.peek().clone());
                            let confirmation = Zeroizing::new(repeat.peek().clone());
                            password.set(String::new());
                            repeat.set(String::new());
                            let cancelled = submit_cancel.clone();
                            spawn(async move {
                                let result: anyhow::Result<()> = async {
                                    if selected == "register" {
                                        let pending = cloud::register(name, address, secret, confirmation)
                                            .await?;
                                        registration
                                            .set(
                                                pending["registration_id"]
                                                    .as_str()
                                                    .ok_or_else(|| {
                                                        anyhow::anyhow!(
                                                            "Сервер не прислал идентификатор регистрации"
                                                        )
                                                    })?
                                                    .into(),
                                            );
                                        mode.set("confirm".into());
                                        message.set("Введите код из письма".into());
                                    } else {
                                        let store = state::store(state)?;
                                        if selected == "confirm" {
                                            cloud::confirm(
                                                    store.clone(),
                                                    registration.peek().clone(),
                                                    code.peek().clone(),
                                                    cancelled,
                                                )
                                                .await?;
                                        } else {
                                            cloud::sign_in(store.clone(), address, secret, cancelled).await?;
                                        }
                                        session.set(cloud::state(&store)?);
                                        mode.set(String::new());
                                        onchange.call(());
                                        message.set("Вход выполнен".into());
                                    }
                                    Ok(())
                                }
                                    .await;
                                if let Err(error) = result {
                                    message.set(error.to_string());
                                }
                                busy.set(false);
                            });
                        },
                        if mode.read().as_str() == "register" {
                            label {
                                class: "field",
                                "Имя"
                                input {
                                    value: "{username}",
                                    maxlength: 50,
                                    required: true,
                                    oninput: move |e| username.set(e.value()),
                                }
                            }
                        }
                        if mode.read().as_str() == "confirm" {
                            label {
                                class: "field",
                                "Код из письма"
                                input {
                                    value: "{code}",
                                    inputmode: "numeric",
                                    maxlength: 6,
                                    required: true,
                                    oninput: move |e| code.set(e.value()),
                                }
                            }
                        } else {
                            label {
                                class: "field",
                                "Email"
                                input {
                                    r#type: "email",
                                    value: "{email}",
                                    autocomplete: "email",
                                    required: true,
                                    oninput: move |e| email.set(e.value()),
                                }
                            }
                            label {
                                class: "field",
                                "Пароль"
                                input {
                                    r#type: "password",
                                    value: "{password}",
                                    autocomplete: if mode.read().as_str() == "register" { "new-password" } else { "current-password" },
                                    required: true,
                                    oninput: move |e| password.set(e.value()),
                                }
                            }
                            if mode.read().as_str() == "register" {
                                label {
                                    class: "field",
                                    "Повторите пароль"
                                    input {
                                        r#type: "password",
                                        value: "{repeat}",
                                        autocomplete: "new-password",
                                        required: true,
                                        oninput: move |e| repeat.set(e.value()),
                                    }
                                }
                            }
                        }
                        div {
                            class: "row",
                            button {
                                class: "button primary",
                                r#type: "submit",
                                disabled: *busy.read(),
                                if *busy.read() {
                                    "Ожидание…"
                                } else if mode.read().as_str() == "register" {
                                    "Создать аккаунт"
                                } else if mode.read().as_str() == "confirm" {
                                    "Подтвердить почту"
                                } else {
                                    "Войти"
                                }
                            }
                            button {
                                class: "button",
                                r#type: "button",
                                disabled: *busy.read(),
                                onclick: move |_| {
                                    mode.set(String::new());
                                    password.set(String::new());
                                    repeat.set(String::new());
                                },
                                "Отмена"
                            }
                        }
                    }
                }
                p {
                    class: "notice",
                    "Google, вход по почте и регистрация требуют работающего сервера."
                }
            }
            if !message.read().is_empty() {
                p {
                    class: "notice",
                    role: "status",
                    "{message}"
                }
            }
        }
    }
}
