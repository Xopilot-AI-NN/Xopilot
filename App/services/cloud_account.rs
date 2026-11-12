// Описание: Прежний контракт аккаунтов /api/v1. Запросы выполняются только по действию пользователя.
use super::db::Store;
use anyhow::{Context, Result, bail, ensure};
use futures_util::StreamExt;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use tokio_util::sync::CancellationToken;
use zeroize::Zeroizing;
pub const KEY: &str = "cloud_account_v1";
/// Определяет адрес сервиса для текущего запроса.
pub fn endpoint() -> String {
    std::env::var("XOPILOT_ACCOUNT_ENDPOINT")
        .unwrap_or_else(|_| "https://xopilot.by".into())
}
/// Разрешает HTTPS и локальный тестовый HTTP без credentials и лишнего пути.
pub fn normalize_endpoint(value: &str) -> Result<String> {
    let url = reqwest::Url::parse(value.trim())?;
    ensure!(
        url.host_str().is_some()
            && url.username().is_empty()
            && url.password().is_none()
            && url.query().is_none()
            && url.fragment().is_none()
            && matches!(url.path(), "" | "/"),
        "Укажите адрес сервера без пути и параметров"
    );
    ensure!(
        url.scheme() == "https"
            || (url.scheme() == "http"
                && matches!(
                    url.host_str(),
                    Some(
                        "localhost" | "127.0.0.1" | "[::1]"
                    )
                )),
        "Серверу нужен HTTPS"
    );
    Ok(url.as_str().trim_end_matches('/').to_owned())
}
/// Читает сохранённую серверную сессию из SQLCipher.
pub fn state(store: &Store) -> Result<Option<Value>> {
    let value: Value = store.read(KEY)?;
    Ok(value["access_token"]
        .as_str()
        .filter(|s| !s.is_empty())
        .map(|_| value.clone()))
}
/// Забывает серверную сессию только на этом устройстве.
pub fn forget(store: &Store) -> Result<()> {
    store.write(KEY, &Value::Null)
}
/// Принимает обычный email без привязки к конкретному почтовому провайдеру.
pub fn validate_email(value: &str) -> Result<String> {
    let value = value.trim().to_ascii_lowercase();
    let parts = value.split('@').collect::<Vec<_>>();
    ensure!(
        value.len() <= 254
            && value.is_ascii()
            && parts.len() == 2
            && !parts[0].is_empty()
            && parts[1].contains('.')
            && !parts[1].starts_with('.')
            && !parts[1].ends_with('.')
            && !value.chars().any(|c| c.is_whitespace()
                || c.is_control()
                || "<>".contains(c)),
        "Введите корректный email — Gmail, Яндекс, Mail.ru или другой почтовый сервис"
    );
    Ok(value)
}
/// Формирует ограниченное имя устройства для серверной сессии.
fn device() -> String {
    std::env::var("HOSTNAME")
        .unwrap_or_else(|_| std::env::consts::OS.into())
        .chars()
        .take(120)
        .collect()
}
// Dioxus может опрашивать Future вне Tokio: сеть всегда живёт в общем runtime.
async fn request(
    endpoint: &str,
    path: &str,
    body: Option<Value>,
    token: Option<&str>,
) -> Result<Value> {
    let endpoint = endpoint.to_owned();
    let path = path.to_owned();
    let token =
        token.map(|value| Zeroizing::new(value.to_owned()));
    super::runtime::background(async move {
        request_inner(
            &endpoint,
            &path,
            body,
            token.as_ref().map(|value| value.as_str()),
        )
        .await
    })
    .await
}
/// Выполняет ограниченный запрос без редиректов и с понятной ошибкой сервера.
async fn request_inner(
    endpoint: &str,
    path: &str,
    body: Option<Value>,
    token: Option<&str>,
) -> Result<Value> {
    let endpoint = normalize_endpoint(endpoint)?;
    let client = super::http_client::builder()?
        .redirect(reqwest::redirect::Policy::none())
        .connect_timeout(std::time::Duration::from_secs(10))
        .timeout(std::time::Duration::from_secs(20))
        .build()?;
    let mut request = if let Some(body) = body {
        client
            .post(format!("{endpoint}/api/v1{path}"))
            .json(&body)
    } else {
        client.get(format!("{endpoint}/api/v1{path}"))
    };
    if let Some(token) = token {
        request = request.bearer_auth(token);
    }
    let response = request
        .send()
        .await
        .context("Сервер аккаунтов недоступен. Повторите после его включения")?;
    let status = response.status();
    let mut stream = response.bytes_stream();
    let mut bytes = Vec::new();
    while let Some(chunk) = stream.next().await {
        let chunk = chunk?;
        ensure!(
            bytes.len() + chunk.len() <= 2 * 1024 * 1024,
            "Слишком большой ответ сервера"
        );
        bytes.extend_from_slice(&chunk);
    }
    let value: Value = serde_json::from_slice(&bytes)
        .context("Сервер вернул неверный ответ")?;
    if !status.is_success() {
        let code = value["error"]
            .as_str()
            .unwrap_or("server_error");
        bail!("{}", error_message(code));
    }
    Ok(value)
}
/// Переводит код ошибки аккаунта в сообщение без секретных данных.
fn error_message(code: &str) -> &str {
    match code {
        "invalid_credentials" => {
            "Неверный email или пароль"
        }
        "email_exists" | "account_exists" => {
            "Аккаунт с такой почтой уже существует"
        }
        "invalid_email" => "Неверный email",
        "password_length" => {
            "Пароль должен содержать не менее 12 символов"
        }
        "invalid_code" => "Неверный код подтверждения",
        "google_not_configured" => {
            "Google ещё не настроен на сервере"
        }
        "google_expired" => "Время входа Google истекло",
        "rate_limited" => {
            "Слишком много попыток. Попробуйте позже"
        }
        "email_unavailable" => {
            "Сервис отправки писем временно недоступен"
        }
        _ => {
            "Не удалось выполнить операцию аккаунта. Проверьте сервер и введённые данные"
        }
    }
}
/// Проверяет профиль, сохраняет токены и отзывает отменённый вход.
async fn persist_login(
    store: &Store,
    endpoint: &str,
    tokens: Value,
    cancelled: &CancellationToken,
) -> Result<()> {
    let access = tokens["access_token"]
        .as_str()
        .context("В ответе нет токена входа")?;
    let profile =
        match request(endpoint, "/me", None, Some(access))
            .await
        {
            Ok(profile) => profile,
            Err(error) => {
                let _ = request(
                    endpoint,
                    "/auth/logout",
                    Some(json!({})),
                    Some(access),
                )
                .await;
                return Err(error);
            }
        };
    if cancelled.is_cancelled() {
        let _ = request(
            endpoint,
            "/auth/logout",
            Some(json!({})),
            Some(access),
        )
        .await;
        bail!("Вход отменён");
    }
    let mut session = tokens;
    let object = session
        .as_object_mut()
        .context("Неверный ответ входа")?;
    for key in [
        "account_id",
        "session_id",
        "username",
        "display_name",
        "email",
        "google_linked",
    ] {
        if let Some(value) = profile.get(key) {
            object.insert(key.into(), value.clone());
        }
    }
    object.insert("endpoint".into(), endpoint.into());
    object.insert("device_name".into(), device().into());
    let expires = object
        .get("expires_in")
        .and_then(Value::as_f64)
        .unwrap_or(0.0);
    object.insert(
        "expires_at".into(),
        json!(super::canvases::now() + expires),
    );
    store.write(KEY, &session)
}
/// Выполняет вход по email через прежний серверный контракт.
pub async fn sign_in(
    store: Store,
    email: String,
    password: Zeroizing<String>,
    cancelled: CancellationToken,
) -> Result<()> {
    ensure!(
        state(&store)?.is_none(),
        "Сначала выйдите из текущего облачного аккаунта"
    );
    let endpoint = normalize_endpoint(&endpoint())?;
    let tokens=request(&endpoint,"/auth/login",Some(json!({"email":validate_email(&email)?,"password":password.as_str(),"device_name":device()})),None).await?;
    persist_login(&store, &endpoint, tokens, &cancelled)
        .await
}
/// Создаёт серверную регистрацию с проверкой имени и совпадения паролей.
pub async fn register(
    username: String,
    email: String,
    password: Zeroizing<String>,
    repeat: Zeroizing<String>,
) -> Result<Value> {
    ensure!(
        password.as_str() == repeat.as_str(),
        "Пароли не совпадают"
    );
    ensure!(
        password.chars().count() >= 12
            && password.len() <= 1024,
        "Пароль: от 12 символов, не более 1024 байт"
    );
    ensure!(
        (2..=50).contains(&username.trim().chars().count())
            && !username.chars().any(char::is_control),
        "Имя: от 2 до 50 символов"
    );
    request(&endpoint(),"/auth/register",Some(json!({"username":username.trim(),"email":validate_email(&email)?,"password":password.as_str(),"device_name":device()})),None).await
}
/// Подтверждает регистрацию шестизначным кодом из письма.
pub async fn confirm(
    store: Store,
    registration: String,
    code: String,
    cancelled: CancellationToken,
) -> Result<()> {
    ensure!(
        uuid::Uuid::parse_str(&registration).is_ok(),
        "Неверная регистрация"
    );
    ensure!(
        code.len() == 6
            && code.chars().all(|c| c.is_ascii_digit()),
        "Введите 6 цифр из письма"
    );
    let endpoint = normalize_endpoint(&endpoint())?;
    let tokens = request(
        &endpoint,
        "/auth/verify-email",
        Some(json!({"registration_id":registration,"code":code})),
        None,
    )
    .await?;
    persist_login(&store, &endpoint, tokens, &cancelled)
        .await
}
pub struct GoogleFlow {
    endpoint: String,
    flow_id: String,
    proof: Zeroizing<String>,
    pub browser_url: String,
}
/// Создаёт временный proof входа и проверяет серверную ссылку браузера.
pub async fn begin_google(
    store: &Store,
) -> Result<GoogleFlow> {
    ensure!(
        state(store)?.is_none(),
        "Сначала выйдите из текущего облачного аккаунта"
    );
    let endpoint = normalize_endpoint(&endpoint())?;
    let proof = Zeroizing::new(format!(
        "{}{}",
        uuid::Uuid::new_v4().simple(),
        uuid::Uuid::new_v4().simple()
    ));
    let pending=request(&endpoint,"/auth/google/start",Some(json!({"proof_hash":hex::encode(Sha256::digest(proof.as_bytes())),"device_name":device(),"link":false})),None).await?;
    let id = uuid::Uuid::parse_str(
        pending["flow_id"]
            .as_str()
            .context("Не указан вход Google")?,
    )?
    .to_string();
    let url = reqwest::Url::parse(
        pending["browser_url"]
            .as_str()
            .context("Не указан адрес входа")?,
    )?;
    ensure!(
        url.origin()
            == reqwest::Url::parse(&endpoint)?.origin()
            && url.fragment().is_none()
            && url.path()
                == format!("/api/v1/auth/google/open/{id}"),
        "Сервер вернул неверную ссылку Google"
    );
    let query = url.query_pairs().collect::<Vec<_>>();
    ensure!(
        query.len() == 1
            && query[0].0 == "ticket"
            && query[0].1.len() == 64
            && query[0]
                .1
                .chars()
                .all(|c| c.is_ascii_hexdigit()),
        "Неверный билет входа Google"
    );
    Ok(GoogleFlow {
        endpoint,
        flow_id: id,
        proof,
        browser_url: url.into(),
    })
}
/// Ожидает завершения Google-входа и сохраняет только подтверждённую сессию.
pub async fn poll_google(
    store: &Store,
    flow: &GoogleFlow,
    cancelled: &CancellationToken,
) -> Result<bool> {
    let response = request(
        &flow.endpoint,
        "/auth/google/poll",
        Some(json!({"flow_id":flow.flow_id,"proof":flow.proof.as_str()})),
        None,
    )
    .await?;
    match response["status"].as_str() {
        Some("pending") => Ok(false),
        Some("authenticated") => {
            persist_login(
                store,
                &flow.endpoint,
                response["tokens"].clone(),
                cancelled,
            )
            .await?;
            Ok(true)
        }
        _ => bail!("Вход Google отменён или истёк"),
    }
}
/// Отзывает незавершённый Google-flow, не сохраняя временный proof.
pub async fn cancel_google(flow: &GoogleFlow) {
    let _ = request(
        &flow.endpoint,
        "/auth/google/cancel",
        Some(json!({"flow_id":flow.flow_id,"proof":flow.proof.as_str()})),
        None,
    )
    .await;
}
