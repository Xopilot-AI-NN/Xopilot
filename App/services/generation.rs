// Описание: Выбранный провайдер один для чата и агента; локальный выбор не отправляет данные в сеть.
use super::{
    api_chat::{self, ApiConfig},
    db::Store,
    model_installer,
};
use anyhow::{Context, Result, ensure};
use serde_json::Value;
use std::path::PathBuf;
use tokio_util::sync::CancellationToken;

#[derive(Clone)]
pub enum Configuration {
    Api(ApiConfig),
    Local { path: PathBuf, backend: String },
}
pub fn selected(store: &Store) -> Result<Configuration> {
    if api_chat::is_api_selected(store)? {
        return Ok(Configuration::Api(api_chat::selected_configuration(store)?));
    }
    let (filename, backend) = store.with(|db| {
        Ok((
            db.get_setting("chat_model")?.unwrap_or_default(),
            db.get_setting("llm_backend")?
                .unwrap_or_else(|| "cpu".into()),
        ))
    })?;
    let spec = model_installer::model(&filename).context("Выберите модель перед отправкой")?;
    ensure!(super::litert::available(), "LiteRT отсутствует в сборке");
    ensure!(
        ["cpu", "gpu"].contains(&backend.as_str()),
        "Неизвестное устройство вычислений"
    );
    Ok(Configuration::Local {
        path: model_installer::installed_path(spec)?,
        backend,
    })
}
pub fn label(store: &Store) -> Result<(String, bool)> {
    if api_chat::is_api_selected(store)? {
        return Ok((api_chat::configuration(store)?.model, false));
    }
    let filename = store.with(|db| Ok(db.get_setting("chat_model")?.unwrap_or_default()))?;
    Ok((
        model_installer::model(&filename)
            .ok()
            .filter(|m| model_installer::installed_path(*m).is_ok())
            .map(|m| m.name.to_owned())
            .unwrap_or_default(),
        true,
    ))
}
pub async fn reply(
    config: Configuration,
    messages: Vec<Value>,
    token: CancellationToken,
    updates: tokio::sync::mpsc::UnboundedSender<String>,
) -> Result<String> {
    match config {
        Configuration::Api(config) => {
            api_chat::generate_reply(config, messages, token, updates).await
        }
        Configuration::Local { path, backend } => {
            super::runtime::blocking(move || {
                super::litert::generate(path, backend, messages, token, updates, 1024)
            })
            .await
        }
    }
}
