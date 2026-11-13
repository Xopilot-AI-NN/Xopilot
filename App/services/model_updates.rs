// Проверка новой версии модели отдельно от загрузки весов.
// Версия фиксируется по commit и SHA-256, чтобы main не изменился во время скачивания.
use super::model_installer::{self, Model};
use anyhow::{Context, Result, ensure};
use serde::{Deserialize, Serialize};
use std::{io::Write, path::PathBuf};
use tokio_util::sync::CancellationToken;

#[derive(
    Clone, Debug, Serialize, Deserialize, PartialEq,
)]
pub struct Revision {
    pub commit: String,
    pub sha256: String,
}

/// Получаю только официальный репозиторий модели из встроенного каталога.
fn repository(spec: Model) -> Result<&'static str> {
    spec.url
        .strip_prefix("https://huggingface.co/")
        .and_then(|value| {
            value.split_once("/resolve/").map(|pair| pair.0)
        })
        .context(
            "Обновление этого источника не поддерживается",
        )
}

/// Проверяю метаданные до записи на диск и до формирования ссылки загрузки.
fn validate(revision: &Revision) -> Result<()> {
    ensure!(
        revision.commit.len() == 40
            && revision
                .commit
                .bytes()
                .all(|b| b.is_ascii_hexdigit()),
        "Неверная версия модели"
    );
    ensure!(
        revision.sha256.len() == 64
            && revision
                .sha256
                .bytes()
                .all(|b| b.is_ascii_hexdigit()),
        "Неверная SHA-256 модели"
    );
    Ok(())
}

/// Не использую изменение описания репозитория как признак обновления весов.
fn parse(
    spec: Model,
    value: &serde_json::Value,
) -> Result<Revision> {
    let file = value["siblings"]
        .as_array()
        .context("Нет списка файлов модели")?
        .iter()
        .find(|file| {
            file["rfilename"].as_str()
                == Some(spec.filename)
        })
        .context(
            "Файл модели отсутствует в новой версии",
        )?;
    let revision = Revision {
        commit: value["sha"]
            .as_str()
            .context("Нет commit модели")?
            .into(),
        sha256: file["lfs"]["sha256"]
            .as_str()
            .context("Нет SHA-256 весов")?
            .into(),
    };
    validate(&revision)?;
    Ok(revision)
}

/// Проверяю обновление в фоне. Переписка и данные профиля в запрос не попадают.
pub async fn check(
    spec: Model,
) -> Result<Option<Revision>> {
    let client = super::http_client::builder()?
        .timeout(std::time::Duration::from_secs(15))
        .build()?;
    let response = client.get(format!("https://huggingface.co/api/models/{}?blobs=true", repository(spec)?))
        .send().await?.error_for_status()?;
    ensure!(
        response.content_length().unwrap_or(0)
            <= 1024 * 1024,
        "Слишком большой ответ каталога"
    );
    let mut response = response;
    let mut bytes = Vec::new();
    while let Some(chunk) = response.chunk().await? {
        ensure!(
            bytes.len() + chunk.len() <= 1024 * 1024,
            "Слишком большой ответ каталога"
        );
        bytes.extend_from_slice(&chunk);
    }
    let latest =
        parse(spec, &serde_json::from_slice(&bytes)?)?;
    let path = model_installer::installed_path(spec)?;
    let digest = super::runtime::blocking(move || {
        model_installer::digest_file(
            &path,
            &CancellationToken::new(),
        )
    })
    .await?;
    Ok((digest != latest.sha256).then_some(latest))
}

/// Сохраняю выбранную версию рядом с весами для продолжения загрузки после перезапуска.
fn path(spec: Model) -> Result<PathBuf> {
    Ok(super::paths::models_dir()?
        .join(format!("{}.revision.json", spec.filename)))
}

/// Возвращаю закреплённую ссылку и ожидаемый хеш для обоих загрузчиков.
pub fn source(spec: Model) -> Result<(String, String)> {
    let path = path(spec)?;
    if !path.exists() {
        return Ok((spec.url.into(), spec.sha256.into()));
    }
    ensure!(
        path.metadata()?.len() < 1024,
        "Повреждены метаданные модели"
    );
    let revision: Revision =
        serde_json::from_slice(&std::fs::read(path)?)?;
    validate(&revision)?;
    Ok((
        format!(
            "https://huggingface.co/{}/resolve/{}/{}?download=true",
            repository(spec)?,
            revision.commit,
            spec.filename
        ),
        revision.sha256,
    ))
}

/// Начинаю обновление без удаления установленной модели. Частичный файл старой версии не смешивается с новым.
pub fn start(
    spec: Model,
    revision: Revision,
) -> Result<()> {
    validate(&revision)?;
    ensure!(
        !["downloading", "verifying", "waiting"].contains(
            &model_installer::progress(spec.id)
                .phase
                .as_str()
        ),
        "Загрузка уже идёт"
    );
    let root = super::paths::models_dir()?;
    std::fs::create_dir_all(&root)?;
    let partial =
        root.join(format!("{}.part", spec.filename));
    if partial.exists() {
        std::fs::remove_file(partial)?;
    }
    let mut file = tempfile::NamedTempFile::new_in(&root)?;
    file.write_all(&serde_json::to_vec(&revision)?)?;
    file.as_file().sync_all()?;
    file.persist(path(spec)?)
        .map_err(|error| error.error)?;
    model_installer::start(spec.id)
}

#[cfg(test)]
mod tests {
    use super::*;
    /// Обновление README не требует скачивать те же веса повторно.
    #[test]
    fn metadata_selects_exact_weight_file() {
        let spec = model_installer::MODELS[0];
        let data = serde_json::json!({"sha": "a".repeat(40), "siblings": [
            {"rfilename":"README.md"},
            {"rfilename":spec.filename,"lfs":{"sha256":spec.sha256}}
        ]});
        assert_eq!(
            parse(spec, &data).unwrap().sha256,
            spec.sha256
        );
        assert!(parse(spec, &serde_json::json!({"sha":"../main","siblings":data["siblings"]})).is_err());
    }
    /// Не принимаю хеш другого файла и неполные сведения каталога.
    #[test]
    fn rejects_missing_or_invalid_digest() {
        let spec = model_installer::MODELS[0];
        assert!(parse(spec, &serde_json::json!({"sha":"a".repeat(40),"siblings":[]})).is_err());
        assert!(
            validate(&Revision {
                commit: "a".repeat(40),
                sha256: "x".repeat(64)
            })
            .is_err()
        );
    }
}
