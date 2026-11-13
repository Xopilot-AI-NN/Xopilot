// Описание: Локальная подготовка аудио и видео через кодеки WebView.
// Кеш привязан к содержимому исходного файла, история хранит исходное вложение.
use super::attachments::{AttachmentParts, MAX_FILE_BYTES};
use anyhow::{Context, Result, bail, ensure};
use base64::{Engine as _, prelude::BASE64_STANDARD};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    io::Read,
    path::{Path, PathBuf},
    time::Duration,
};
use tokio_util::sync::CancellationToken;

const MAX_CACHE: u64 = 8 * 1024 * 1024;

#[derive(Serialize, Deserialize)]
pub(super) struct Frame {
    pub(super) seconds: f64,
    pub(super) data: String,
}
#[derive(Serialize, Deserialize)]
pub(super) struct Prepared {
    pub(super) duration: f64,
    pub(super) frames: Vec<Frame>,
    pub(super) audio: Option<String>,
    pub(super) warning: String,
}
#[derive(Serialize, Deserialize)]
struct Response {
    ok: bool,
    #[serde(default)]
    error: String,
    result: Option<Prepared>,
}

/// Возвращает MIME и тип поддерживаемого медиафайла по расширению.
fn kind(path: &Path) -> Option<(&'static str, bool)> {
    match path
        .extension()?
        .to_str()?
        .to_ascii_lowercase()
        .as_str()
    {
        "wav" => Some(("audio/wav", false)),
        "mp3" => Some(("audio/mpeg", false)),
        "ogg" | "oga" | "opus" => {
            Some(("audio/ogg", false))
        }
        "flac" => Some(("audio/flac", false)),
        "m4a" => Some(("audio/mp4", false)),
        "aac" => Some(("audio/aac", false)),
        "mp4" | "m4v" => Some(("video/mp4", true)),
        "mov" => Some(("video/quicktime", true)),
        "webm" => Some(("video/webm", true)),
        "mkv" => Some(("video/x-matroska", true)),
        "avi" => Some(("video/x-msvideo", true)),
        _ => None,
    }
}

/// Кеш версии v1 меняется вместе с содержимым файла и не затрагивает оригинал.
fn cache_path(
    path: &Path,
    bytes: &[u8],
) -> Result<PathBuf> {
    let digest = hex::encode(Sha256::digest(bytes));
    let extension = path
        .extension()
        .unwrap_or_default()
        .to_string_lossy();
    Ok(super::paths::app_data_dir()?
        .join("media-cache-v1")
        .join(format!("{digest}-{extension}.json")))
}

/// Проверяет размеры и формат результата перед использованием в контексте модели.
pub(super) fn validate(prepared: &Prepared) -> Result<()> {
    ensure!(
        prepared.duration.is_finite()
            && prepared.duration > 0.0
            && prepared.duration <= 30.01,
        "Медиа должно быть длительностью до 30 секунд"
    );
    ensure!(
        prepared.frames.len() <= 4
            && (!prepared.frames.is_empty()
                || prepared.audio.is_some()),
        "В файле нет доступного звука или кадров"
    );
    for frame in &prepared.frames {
        ensure!(
            frame.seconds.is_finite()
                && frame.seconds >= 0.0
                && frame.seconds <= prepared.duration,
            "Неверное время кадра"
        );
        let bytes = BASE64_STANDARD.decode(&frame.data)?;
        ensure!(
            bytes.len() <= 1024 * 1024
                && bytes.starts_with(&[0xff, 0xd8]),
            "Повреждён кадр видео"
        );
    }
    if let Some(audio) = &prepared.audio {
        validate_wav(&BASE64_STANDARD.decode(audio)?)?;
    }
    Ok(())
}

/// Проверяет фиксированный WAV PCM16, который создаёт локальный декодер.
/// Проверка повторяется перед C API, включая размер данных и частоту дискретизации.
pub(crate) fn validate_wav(bytes: &[u8]) -> Result<()> {
    ensure!(
        bytes.len() >= 46 && bytes.len() <= 960046,
        "Аудио должно длиться до 30 секунд"
    );
    ensure!(
        &bytes[..4] == b"RIFF"
            && &bytes[8..12] == b"WAVE"
            && &bytes[12..16] == b"fmt "
            && &bytes[36..40] == b"data",
        "Повреждён подготовленный WAV"
    );
    ensure!(
        u16::from_le_bytes(bytes[20..22].try_into()?) == 1
            && u16::from_le_bytes(
                bytes[22..24].try_into()?
            ) == 1
            && u16::from_le_bytes(
                bytes[34..36].try_into()?
            ) == 16
            && u32::from_le_bytes(
                bytes[24..28].try_into()?
            ) == 16000,
        "Нужен WAV PCM16 mono 16 кГц"
    );
    ensure!(
        u32::from_le_bytes(bytes[40..44].try_into()?)
            as usize
            == bytes.len() - 44
            && (bytes.len() - 44).is_multiple_of(2),
        "Неверный размер звуковых данных"
    );
    Ok(())
}

/// Читает ограниченный JSON-кеш. Ошибки подготовки сохраняются для пояснения
/// в чате, следующий запрос повторяет попытку вместо вечного кеширования ошибки.
fn cached(path: &Path) -> Result<Response> {
    let mut bytes = Vec::new();
    std::fs::File::open(path)?
        .take(MAX_CACHE + 1)
        .read_to_end(&mut bytes)?;
    ensure!(
        bytes.len() as u64 <= MAX_CACHE,
        "Кеш медиа слишком большой"
    );
    Ok(serde_json::from_slice(&bytes)?)
}

/// Преобразует подготовленные кадры и звук в общие части вложений.
pub fn read(
    path: &Path,
    bytes: &[u8],
) -> Result<AttachmentParts> {
    let response = cached(&cache_path(path, bytes)?)
        .context("Медиа ещё не подготовлено")?;
    ensure!(response.ok, "{}", response.error);
    let result = response
        .result
        .context("Пустой результат подготовки медиа")?;
    validate(&result)?;
    let mut parts = AttachmentParts::default();
    let note = if result.frames.is_empty() {
        format!(
            "Аудио: {:.2} с. {}",
            result.duration, result.warning
        )
    } else {
        format!(
            "Видео: {:.2} с. Показаны {} выбранных кадров в хронологическом порядке. Временные отметки: {}. {}",
            result.duration,
            result.frames.len(),
            result
                .frames
                .iter()
                .map(|frame| format!(
                    "{:.2} с",
                    frame.seconds
                ))
                .collect::<Vec<_>>()
                .join(", "),
            result.warning
        )
    };
    parts.text_notes.push(note);
    for frame in result.frames {
        parts
            .images
            .push(BASE64_STANDARD.decode(frame.data)?);
    }
    if let Some(audio) = result.audio {
        parts.audio.push(BASE64_STANDARD.decode(audio)?);
    }
    Ok(parts)
}

/// Декодирует новое медиа в UI-контексте, где доступен мост Dioxus ↔ WebView.
/// Долгое чтение и запись идут в worker, модель и её KV-кеш не пересоздаются.
pub async fn prepare_history(
    history: &[advanced_xopilot::db::StoredMessage],
    token: &CancellationToken,
) -> Result<()> {
    for message in history {
        for (_, path) in &message.attachments {
            let path = PathBuf::from(path);
            let Some((mime, video)) = kind(&path) else {
                continue;
            };
            ensure!(
                !token.is_cancelled(),
                "Подготовка медиа отменена"
            );
            let worker_token = token.clone();
            let loaded =
                super::runtime::blocking(move || {
                    let mut bytes = Vec::new();
                    std::fs::File::open(&path)?
                        .take(MAX_FILE_BYTES + 1)
                        .read_to_end(&mut bytes)?;
                    ensure!(
                        bytes.len() as u64
                            <= MAX_FILE_BYTES,
                        "Размер файла превышает 32 МиБ"
                    );
                    let cache = cache_path(&path, &bytes)?;
                    let ready = cached(&cache).is_ok_and(
                        |response| {
                            response.ok
                                && response
                                    .result
                                    .as_ref()
                                    .is_some_and(|result| {
                                        validate(result)
                                            .is_ok()
                                    })
                        },
                    );
                    let native = if ready {
                        None
                    } else {
                        match super::media_codecs::prepare(
                            &path,
                            &bytes,
                            video,
                            &worker_token,
                        ) {
                            Ok(result) => Some(Response {
                                ok: true,
                                error: String::new(),
                                result: Some(result),
                            }),
                            Err(error) if error.is::<super::media_codecs::DurationLimit>() => Some(Response {
                                ok: false,
                                error: error.to_string(),
                                result: None,
                            }),
                            Err(error) => {
                                tracing::debug!("Встроенный декодер не прочитал медиа: {error}");
                                None
                            }
                        }
                    };
                    Ok((bytes, cache, ready, native))
                })
                .await;
            let (bytes, cache, ready, native) = match loaded
            {
                Ok(value) => value,
                Err(error) => {
                    tracing::warn!(
                        "Не удалось подготовить вложение: {error}"
                    );
                    continue;
                }
            };
            if ready {
                continue;
            }
            ensure!(
                !token.is_cancelled(),
                "Подготовка медиа отменена"
            );
            let response = if let Some(response) = native {
                response
            } else {
                let mut bridge = dioxus::document::eval(
                    include_str!("media.js"),
                );
                bridge.send(serde_json::json!({"data":BASE64_STANDARD.encode(bytes),"mime":mime,"video":video}))?;
                tokio::select! {
                    _ = token.cancelled() => bail!("Подготовка медиа отменена"),
                    result = tokio::time::timeout(Duration::from_secs(65), bridge.recv::<Response>()) => {
                        match result {
                            Ok(Ok(response)) => response,
                            Ok(Err(error)) => Response { ok:false, error:format!("Ошибка моста декодирования: {error}"), result:None },
                            Err(_) => Response { ok:false, error:"Истекло время подготовки медиа".into(), result:None },
                        }
                    }
                }
            };
            if let Some(result) = &response.result {
                validate(result)?;
            }
            super::runtime::blocking(move || {
                std::fs::create_dir_all(
                    cache.parent().unwrap(),
                )?;
                let mut temporary =
                    tempfile::NamedTempFile::new_in(
                        cache.parent().unwrap(),
                    )?;
                let bytes = serde_json::to_vec(&response)?;
                ensure!(
                    bytes.len() as u64 <= MAX_CACHE,
                    "Кеш медиа слишком большой"
                );
                std::io::Write::write_all(
                    temporary.as_file_mut(),
                    &bytes,
                )?;
                temporary
                    .persist(&cache)
                    .map_err(|error| error.error)?;
                Ok(())
            })
            .await?;
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Фиксируем поддерживаемые контейнеры без попытки читать двоичные данные как текст.
    #[test]
    fn recognizes_audio_and_video_extensions() {
        assert_eq!(
            kind(Path::new("VOICE.MP3")),
            Some(("audio/mpeg", false))
        );
        assert_eq!(
            kind(Path::new("clip.mp4")),
            Some(("video/mp4", true))
        );
        assert_eq!(kind(Path::new("data.txt")), None);
    }

    /// Неверная длительность, количество кадров и повреждённый звук не попадают в модель.
    #[test]
    fn rejects_invalid_prepared_payloads() {
        let mut prepared = Prepared {
            duration: 1.0,
            frames: vec![],
            audio: None,
            warning: String::new(),
        };
        assert!(validate(&prepared).is_err());
        prepared.audio =
            Some(BASE64_STANDARD.encode(b"RIFF"));
        assert!(validate(&prepared).is_err());
        prepared.duration = f64::NAN;
        assert!(validate(&prepared).is_err());
        assert!(validate_wav(&[0; 44]).is_err());
        assert!(validate_wav(&vec![0; 960048]).is_err());
    }
}
