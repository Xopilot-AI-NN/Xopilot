// Файл: App/services/api_chat.rs
// Описание: Потоковый совместимый API; поддерживает также локальный llama-server/Ollama.
use super::{attachments::build_attachment_message_parts, db::Store};
use advanced_xopilot::db::StoredMessage;
use anyhow::{Context, Result, bail, ensure};
use base64::{Engine, prelude::BASE64_STANDARD};
use futures_util::StreamExt;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::time::Duration;
use tokio_util::sync::CancellationToken;

pub const KEY: &str = "api_config_v1";

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct ApiConfig {
    pub url: String,
    pub model: String,
    pub key: String,
}

impl ApiConfig {
    pub fn validate(&self) -> Result<Self> {
        let url = reqwest::Url::parse(self.url.trim())
            .context("Введите URL API: https://example.com/v1")?;
        ensure!(
            url.username().is_empty()
                && url.password().is_none()
                && url.query().is_none()
                && url.fragment().is_none(),
            "URL не должен содержать пароль или параметры"
        );
        let local = matches!(
            url.host_str(),
            Some("localhost" | "127.0.0.1" | "[::1]" | "::1")
        );
        ensure!(
            url.scheme() == "https" || (url.scheme() == "http" && local),
            "Удалённому API нужен HTTPS; HTTP разрешён для localhost"
        );
        ensure!(
            url.host_str().is_some() && !self.model.trim().is_empty(),
            "Введите адрес и идентификатор модели"
        );
        Ok(Self {
            url: self.url.trim().trim_end_matches('/').into(),
            model: self.model.trim().into(),
            key: self.key.trim().into(),
        })
    }
}

pub fn configuration(store: &Store) -> Result<ApiConfig> {
    store.read(KEY)
}

pub fn is_api_selected(store: &Store) -> Result<bool> {
    store.with(|db| Ok(db.get_setting("chat_provider")?.as_deref() == Some("api")))
}

/// Сам факт сохранённого ключа не разрешает переключать прежний локальный чат на сеть.
pub fn selected_configuration(store: &Store) -> Result<ApiConfig> {
    ensure!(
        is_api_selected(store)?,
        "API не выбран. Выберите локальную модель или сохраните подключение API"
    );
    configuration(store)?.validate()
}

pub fn save_configuration(store: &Store, config: &ApiConfig) -> Result<()> {
    store.write(KEY, &config.validate()?)?;
    store.with(|db| {
        db.set_setting("chat_provider", "api")?;
        Ok(())
    })
}

pub fn endpoint(config: &ApiConfig) -> String {
    format!("{}/chat/completions", config.url.trim_end_matches('/'))
}

/// Полная история остаётся в БД. Лимит API не выдумываем: превышение возвращает провайдер.
/// Изображения и файлы исторических сообщений тоже передаются выбранной модели.
pub fn build_messages(history: &[StoredMessage], instructions: &str) -> Vec<Value> {
    let mut messages = vec![json!({"role": "system", "content": format!(
        "Ты Xopilot, полезный ИИ-помощник. Отвечай на языке пользователя. Не утверждай, что выполнил действие, если у тебя нет результата инструмента.\n{instructions}")})];
    for message in history {
        let role = if message.role == "ai" || message.role == "assistant" {
            "assistant"
        } else {
            "user"
        };
        let parts = build_attachment_message_parts(&message.attachments);
        let mut text = message.content.clone();
        if let Some(quote) = &message.quote {
            text.push_str(&format!("\nЦитата:\n{quote}"));
        }
        if let Some(reply) = &message.reply_to {
            text.push_str(&format!("\nОтвет на:\n{reply}"));
        }
        for note in parts.text_notes {
            text.push('\n');
            text.push_str(&note);
        }
        let mut content = vec![json!({"type":"text", "text":text})];
        for image in parts.images {
            content.push(json!({"type":"image_url", "image_url":{"url":format!("data:image/jpeg;base64,{}", BASE64_STANDARD.encode(image))}}));
        }
        messages.push(json!({"role": role, "content": if content.len() == 1 { content[0]["text"].clone() } else { json!(content) }}));
    }
    messages
}

#[derive(Default)]
pub struct EventDecoder {
    buffer: Vec<u8>,
}

impl EventDecoder {
    /// SSE может разбить UTF-8, JSON и CRLF между любыми сетевыми чанками.
    pub fn push(&mut self, chunk: &[u8]) -> Result<Vec<String>> {
        self.buffer.extend_from_slice(chunk);
        ensure!(
            self.buffer.len() <= 4 * 1024 * 1024,
            "Слишком большое событие API"
        );
        let mut lines = Vec::new();
        while let Some(end) = self.buffer.iter().position(|b| *b == b'\n') {
            let mut line: Vec<u8> = self.buffer.drain(..=end).collect();
            while line.last().is_some_and(|b| *b == b'\n' || *b == b'\r') {
                line.pop();
            }
            lines.push(String::from_utf8(line).context("API вернул неверный UTF-8")?);
        }
        Ok(lines)
    }

    pub fn finish(&mut self) -> Result<Vec<String>> {
        if self.buffer.is_empty() {
            return Ok(vec![]);
        }
        self.push(b"\n")
    }
}

fn decode_line(line: &str) -> Result<(Option<String>, bool)> {
    let Some(data) = line.strip_prefix("data:") else {
        return Ok((None, false));
    };
    let data = data.trim();
    if data == "[DONE]" {
        return Ok((None, true));
    }
    if data.is_empty() {
        return Ok((None, false));
    }
    let value: Value = serde_json::from_str(data).context("API вернул неверное событие")?;
    if let Some(error) = value.get("error") {
        bail!(
            "Ошибка API: {}",
            error
                .get("message")
                .and_then(Value::as_str)
                .unwrap_or("запрос отклонён")
        );
    }
    let delta = &value["choices"][0]["delta"]["content"];
    Ok((delta.as_str().map(str::to_owned), false))
}

pub async fn generate_reply(
    config: ApiConfig,
    messages: Vec<Value>,
    cancelled: CancellationToken,
    updates: tokio::sync::mpsc::UnboundedSender<String>,
) -> Result<String> {
    let config = config.validate()?;
    let client = reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(15))
        .timeout(Duration::from_secs(600))
        // Ключ API нельзя пересылать на адрес из редиректа.
        .redirect(reqwest::redirect::Policy::none())
        .build()?;
    let mut request = client.post(endpoint(&config)).json(&json!({
        "model": config.model, "messages": messages, "stream": true,
    }));
    if !config.key.is_empty() {
        request = request.bearer_auth(&config.key);
    }
    let response = tokio::select! {
        _ = cancelled.cancelled() => bail!("Запрос отменён"),
        response = request.send() => response.context("Не удалось подключиться к API")?,
    };
    let status = response.status();
    ensure!(
        status.is_success(),
        "API вернул HTTP {}. Проверьте модель, адрес и доступ к провайдеру.",
        status.as_u16()
    );
    let is_json = response
        .headers()
        .get(reqwest::header::CONTENT_TYPE)
        .and_then(|h| h.to_str().ok())
        .is_some_and(|s| s.contains("application/json"));
    let mut stream = response.bytes_stream();
    let mut decoder = EventDecoder::default();
    let mut answer = String::new();
    let mut json_body = Vec::new();
    loop {
        let chunk = tokio::select! {
            _ = cancelled.cancelled() => bail!("Запрос отменён"),
            result = tokio::time::timeout(Duration::from_secs(120), stream.next()) => result.context("API не ответил за 120 секунд")?,
        };
        let Some(chunk) = chunk else {
            break;
        };
        let chunk = chunk.context("Соединение с API прервано")?;
        if is_json {
            ensure!(
                json_body.len() + chunk.len() <= 8 * 1024 * 1024,
                "Ответ API превышает 8 МиБ"
            );
            json_body.extend_from_slice(&chunk);
            continue;
        }
        for line in decoder.push(&chunk)? {
            let (text, done) = decode_line(&line)?;
            if let Some(text) = text {
                answer.push_str(&text);
                let _ = updates.send(text);
            }
            ensure!(answer.len() <= 8 * 1024 * 1024, "Ответ API превышает 8 МиБ");
            if done {
                ensure!(!answer.trim().is_empty(), "Модель вернула пустой ответ");
                return Ok(answer);
            }
        }
    }
    if is_json {
        let value: Value = serde_json::from_slice(&json_body)?;
        answer = value["choices"][0]["message"]["content"]
            .as_str()
            .unwrap_or_default()
            .into();
        let _ = updates.send(answer.clone());
    } else {
        for line in decoder.finish()? {
            if let (Some(text), _) = decode_line(&line)? {
                answer.push_str(&text);
                let _ = updates.send(text);
            }
        }
    }
    ensure!(!answer.trim().is_empty(), "Модель вернула пустой ответ");
    Ok(answer)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn url_rejects_remote_http_credentials_and_query() {
        for url in [
            "http://example.com/v1",
            "https://u:p@example.com/v1",
            "https://example.com/v1?key=secret",
        ] {
            assert!(
                ApiConfig {
                    url: url.into(),
                    model: "m".into(),
                    key: String::new()
                }
                .validate()
                .is_err()
            );
        }
        assert!(
            ApiConfig {
                url: "http://localhost:8080/v1".into(),
                model: "m".into(),
                key: String::new()
            }
            .validate()
            .is_ok()
        );
    }
    #[test]
    fn stream_survives_fragmented_unicode_and_crlf() {
        let raw = "data: {\"choices\":[{\"delta\":{\"content\":\"Привет\"}}]}\r\n\r\ndata: [DONE]";
        let mut decoder = EventDecoder::default();
        let mut lines = Vec::new();
        for byte in raw.as_bytes() {
            lines.extend(decoder.push(&[*byte]).unwrap());
        }
        lines.extend(decoder.finish().unwrap());
        assert_eq!(decode_line(&lines[0]).unwrap().0.as_deref(), Some("Привет"));
        assert!(decode_line(&lines[2]).unwrap().1);
    }
}
