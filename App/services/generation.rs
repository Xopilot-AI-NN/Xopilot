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

#[derive(Clone, PartialEq)]
pub enum Configuration {
    Api(ApiConfig),
    Local { path: PathBuf, backend: String },
}
/// Разрешает явный выбор провайдера и устройства для запроса.
pub fn selected(store: &Store) -> Result<Configuration> {
    if api_chat::is_api_selected(store)? {
        return Ok(Configuration::Api(api_chat::selected_configuration(store)?));
    }
    let (filename, backend) = store.with(|db| {
        Ok((
            db.get_setting("chat_model")?.unwrap_or_default(),
            db.get_setting("llm_backend")?
                .unwrap_or_else(|| "auto".into()),
        ))
    })?;
    let spec = model_installer::model(&filename).context("Выберите модель перед отправкой")?;
    ensure!(super::litert::available(), "LiteRT отсутствует в сборке");
    ensure!(
        ["auto", "cpu", "gpu"].contains(&backend.as_str()),
        "Неизвестное устройство вычислений"
    );
    Ok(Configuration::Local {
        path: model_installer::installed_path(spec)?,
        backend,
    })
}
/// Возвращает название действительно доступной модели для строки ввода.
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
/// Выполняет запрос выбранной модели и возвращает итоговый текст.
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
            let automatic = backend == "auto";
            let (chosen, reason) = if automatic {
                if let Some(loaded) = super::litert::loaded_backend(&path) {
                    (loaded, "Повторно используем загруженную модель".into())
                } else {
                    // Освобождаем прежнюю модель до замера: её VRAM не должна мешать новому выбору.
                    super::litert::unload()?;
                    let size = path.metadata()?.len();
                    let (chosen, reason) = super::compute::choose(size).await;
                    (chosen.into(), reason)
                }
            } else {
                (backend, "Устройство выбрано вручную".into())
            };
            let loading = super::litert::loaded_backend(&path).as_deref() != Some(chosen.as_str());
            super::compute::set(&chosen, &reason, loading);
            let mut result = attempt(
                path.clone(),
                chosen.clone(),
                messages.clone(),
                token.clone(),
                updates.clone(),
            )
            .await;
            if automatic
                && chosen == "gpu"
                && result.0.is_err()
                && !result.1
                && !token.is_cancelled()
            {
                super::compute::set(
                    "cpu",
                    "GPU не запустился; автоматически переходим на CPU",
                    true,
                );
                result = attempt(path, "cpu".into(), messages, token, updates).await;
                super::compute::set("cpu", "GPU недоступен; используется CPU", false);
            } else {
                super::compute::set(&chosen, &reason, false);
            }
            result.0
        }
    }
}

/// Пересылает токены и отмечает первый вывод: после него повторный запуск запрещён.
async fn attempt(
    path: PathBuf,
    backend: String,
    messages: Vec<Value>,
    token: CancellationToken,
    updates: tokio::sync::mpsc::UnboundedSender<String>,
) -> (Result<String>, bool) {
    let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel::<String>();
    let relay = tokio::spawn(async move {
        let mut emitted = false;
        while let Some(text) = rx.recv().await {
            emitted |= !text.is_empty();
            let _ = updates.send(text);
        }
        emitted
    });
    let result = super::runtime::blocking(move || {
        super::litert::generate(path, backend, messages, token, tx, 1024)
    })
    .await;
    let emitted = relay.await.unwrap_or(true);
    (result, emitted)
}
