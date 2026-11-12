// Описание: Проверяем опубликованный стабильный релиз только по нажатию кнопки.
use anyhow::{Context, Result, ensure};
#[derive(Clone, Debug)]
pub struct Release {
    pub version: String,
    pub notes: String,
    pub url: String,
}
/// Проверяет опубликованный стабильный релиз по действию пользователя.
pub async fn latest() -> Result<Option<Release>> {
    let response = super::http_client::builder()?
        .timeout(std::time::Duration::from_secs(20))
        .build()?
        .get("https://api.github.com/repos/Xopilot-AI-NN/Xopilot/releases/latest")
        .header("User-Agent", concat!("Xopilot/", env!("CARGO_PKG_VERSION")))
        .send()
        .await
        .context("Не удалось связаться с GitHub")?;
    if response.status() == reqwest::StatusCode::NOT_FOUND {
        return Ok(None);
    }
    let response = response.error_for_status()?;
    ensure!(
        response.content_length().unwrap_or(0)
            <= 1024 * 1024,
        "Ответ обновлений слишком большой"
    );
    use futures_util::StreamExt;
    let mut stream = response.bytes_stream();
    let mut bytes = Vec::new();
    while let Some(chunk) = stream.next().await {
        let chunk = chunk?;
        ensure!(
            bytes.len() + chunk.len() <= 1024 * 1024,
            "Ответ обновлений слишком большой"
        );
        bytes.extend_from_slice(&chunk);
    }
    let value: serde_json::Value =
        serde_json::from_slice(&bytes)?;
    let version = value["tag_name"]
        .as_str()
        .context("Релиз без версии")?
        .to_owned();
    let url = value["html_url"]
        .as_str()
        .context("Релиз без ссылки")?
        .to_owned();
    ensure!(
        url.starts_with("https://github.com/Xopilot-AI-NN/Xopilot/releases/tag/"),
        "Неверная ссылка релиза"
    );
    Ok(Some(Release {
        version,
        notes: value["body"]
            .as_str()
            .unwrap_or_default()
            .to_owned(),
        url,
    }))
}
