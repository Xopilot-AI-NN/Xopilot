// Описание: Потоковая загрузка с паузой/продолжением, межпроцессной блокировкой и SHA-256.
use super::db::Store;
use anyhow::{Context, Result, ensure};
#[cfg(any(not(target_os = "android"), test))]
use futures_util::StreamExt;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::HashMap,
    io::Read,
    path::{Path, PathBuf},
    sync::{Mutex, OnceLock},
};
use tokio_util::sync::CancellationToken;

#[derive(Clone, Copy)]
pub struct Model {
    pub id: &'static str,
    pub name: &'static str,
    pub filename: &'static str,
    pub size: &'static str,
    pub url: &'static str,
    pub sha256: &'static str,
}
pub const MODELS: &[Model] = &[
    Model {
        id: "gemma-4-e2b",
        name: "Gemma4-e2b",
        filename: "gemma-4-E2B-it.litertlm",
        size: "2.59 GB",
        url: "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it.litertlm?download=true",
        sha256: "181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c",
    },
    Model {
        id: "gemma-4-e4b",
        name: "Gemma4-e4b",
        filename: "gemma-4-E4B-it.litertlm",
        size: "3.66 GB",
        url: "https://huggingface.co/litert-community/gemma-4-E4B-it-litert-lm/resolve/main/gemma-4-E4B-it.litertlm?download=true",
        sha256: "0b2a8980ce155fd97673d8e820b4d29d9c7d99b8fa6806f425d969b145bd52e0",
    },
    // Универсальный артефакт CPU/GPU, отдельная GPU-only сборка не подходит fallback CPU.
    Model {
        id: "gemma4:12b",
        name: "Gemma 4 12B",
        filename: "gemma-4-12B-it.litertlm",
        size: "6.88 GB",
        url: "https://huggingface.co/litert-community/gemma-4-12B-it-litert-lm/resolve/main/gemma-4-12B-it.litertlm?download=true",
        sha256: "58fd31b778ca2c21c80d634fb34fc5a89d11d563a38dfd3cbf1b40dbf252a8b6",
    },
];
/// Находит поддерживаемую модель по ID или имени файла.
pub fn model(id: &str) -> Result<Model> {
    MODELS
        .iter()
        .find(|m| m.id == id || m.filename == id)
        .copied()
        .context("Модель отсутствует в каталоге")
}
/// Находит установленный файл, включая совместимый прежний каталог.
pub fn installed_path(spec: Model) -> Result<PathBuf> {
    let path =
        super::paths::models_dir()?.join(spec.filename);
    if path.is_file() {
        return Ok(path);
    }
    let legacy = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("data/models")
        .join(spec.filename);
    if legacy.is_file() {
        return Ok(legacy);
    }
    anyhow::bail!("Сначала скачайте {}", spec.name)
}
/// Вычисляет SHA-256 потоком, проверяя отмену между блоками.
pub fn digest_file(
    path: &Path,
    token: &CancellationToken,
) -> Result<String> {
    let mut source = std::fs::File::open(path)?;
    let mut hash = Sha256::new();
    let mut buffer = vec![0; 1024 * 1024];
    loop {
        ensure!(
            !token.is_cancelled(),
            "Операция приостановлена"
        );
        let count = source.read(&mut buffer)?;
        if count == 0 {
            break;
        }
        hash.update(&buffer[..count]);
    }
    Ok(hex::encode(hash.finalize()))
}
#[derive(
    Clone, Default, Debug, PartialEq, Serialize, Deserialize,
)]
pub struct Progress {
    pub phase: String,
    pub downloaded: u64,
    pub total: Option<u64>,
    pub error: String,
}
struct Job {
    progress: Progress,
    token: CancellationToken,
}
static JOBS: OnceLock<Mutex<HashMap<String, Job>>> =
    OnceLock::new();
/// Лениво создаёт общий реестр фоновых загрузок.
fn jobs() -> &'static Mutex<HashMap<String, Job>> {
    JOBS.get_or_init(|| Mutex::new(HashMap::new()))
}
/// Публикует снимок прогресса для окна и общей полосы состояния.
fn notify(
    id: &str,
    phase: &str,
    downloaded: u64,
    total: Option<u64>,
    error: String,
) {
    if let Ok(mut jobs) = jobs().lock()
        && let Some(job) = jobs.get_mut(id)
    {
        job.progress = Progress {
            phase: phase.into(),
            downloaded,
            total,
            error,
        };
    }
}
/// Возвращает текущую фазу, объём и ошибку операции.
pub fn progress(id: &str) -> Progress {
    #[cfg(target_os = "android")]
    if let Some(progress) =
        super::android_downloads::progress(id)
    {
        return progress;
    }
    if let Ok(jobs) = jobs().lock()
        && let Some(job) = jobs.get(id)
    {
        return job.progress.clone();
    }
    let mut result = Progress::default();
    if let Ok(spec) = model(id) {
        if installed_path(spec).is_ok() {
            result.phase = "installed".into();
        } else if let Ok(root) = super::paths::models_dir()
            && let Ok(metadata) = root
                .join(format!("{}.part", spec.filename))
                .metadata()
        {
            result.phase = "paused".into();
            result.downloaded = metadata.len();
        }
    }
    result
}
/// Запрашивает остановку загрузки с сохранением частичного файла.
pub fn pause(id: &str) {
    if let Ok(jobs) = jobs().lock()
        && let Some(job) = jobs.get(id)
    {
        job.token.cancel();
    }
}
/// Начинает операцию после проверки размера и исключения параллельной записи.
pub fn start(id: &str) -> Result<()> {
    let spec = model(id)?;
    #[cfg(target_os = "android")]
    return super::android_downloads::start(spec);
    #[cfg(not(target_os = "android"))]
    start_native(spec)
}

/// Настольная потоковая загрузка сохраняет прежнюю ручную паузу и Range-продолжение.
#[cfg(not(target_os = "android"))]
fn start_native(spec: Model) -> Result<()> {
    let token = CancellationToken::new();
    {
        let mut jobs = jobs().lock().map_err(|_| {
            anyhow::anyhow!("Ошибка загрузчика")
        })?;
        ensure!(
            !jobs.get(spec.id).is_some_and(|j| [
                "downloading",
                "verifying"
            ]
            .contains(&j.progress.phase.as_str())),
            "Загрузка уже идёт"
        );
        jobs.insert(
            spec.id.into(),
            Job {
                progress: Progress {
                    phase: "downloading".into(),
                    ..Default::default()
                },
                token: token.clone(),
            },
        );
    }
    super::runtime::runtime().spawn(async move {
        let result = download(spec, token.clone()).await;
        if let Err(error) = result {
            let current = progress(spec.id);
            notify(
                spec.id,
                if token.is_cancelled() {
                    "paused"
                } else {
                    "error"
                },
                current.downloaded,
                current.total,
                if token.is_cancelled() {
                    String::new()
                } else {
                    format!("{error:#}")
                },
            );
        }
    });
    Ok(())
}
/// Не допускает одновременной установки одной модели несколькими процессами.
fn lock(root: &Path, spec: Model) -> Result<std::fs::File> {
    std::fs::create_dir_all(root)?;
    let lock = std::fs::OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(root.join(format!(
            "{}.part.lock",
            spec.filename
        )))?;
    fs2::FileExt::try_lock_exclusive(&lock)
        .context("Модель занята другим процессом")?;
    Ok(lock)
}
/// Отменяет системную Android-загрузку; на ПК оставляет совместимую паузу.
pub fn cancel(id: &str) -> Result<()> {
    #[cfg(target_os = "android")]
    return super::android_downloads::cancel(id);
    #[cfg(not(target_os = "android"))]
    {
        pause(id);
        Ok(())
    }
}
/// Запускает сетевую загрузку и отражает её завершение в реестре.
#[cfg(not(target_os = "android"))]
async fn download(
    spec: Model,
    token: CancellationToken,
) -> Result<()> {
    let root = super::paths::models_dir()?;
    download_to(spec, token, root).await
}
/// Продолжает частичный файл и публикует его только после проверки SHA-256.
#[cfg(any(not(target_os = "android"), test))]
async fn download_to(
    spec: Model,
    token: CancellationToken,
    root: PathBuf,
) -> Result<()> {
    let _lease = lock(&root, spec)?;
    let part = root.join(format!("{}.part", spec.filename));
    let mut offset =
        part.metadata().map(|m| m.len()).unwrap_or(0);
    let (url, expected_digest) =
        super::model_updates::source(spec)?;
    let client = super::http_client::builder()?
        .connect_timeout(std::time::Duration::from_secs(15))
        .build()?;
    let mut request = client
        .get(url)
        .header("Accept-Encoding", "identity");
    if offset > 0 {
        request = request
            .header("Range", format!("bytes={offset}-"));
    }
    let response = tokio::select! { _=token.cancelled()=>anyhow::bail!("Пауза"), response=tokio::time::timeout(std::time::Duration::from_secs(60),request.send())=>response.context("Сервер модели не ответил; загруженная часть сохранена")?.context("Нет соединения; загруженная часть сохранена")? };
    let total;
    if response.status()
        == reqwest::StatusCode::RANGE_NOT_SATISFIABLE
        && offset > 0
    {
        total = Some(offset);
    } else {
        ensure!(
            response.status().is_success(),
            "Сервер модели вернул HTTP {}",
            response.status()
        );
        if response.status()
            == reqwest::StatusCode::PARTIAL_CONTENT
        {
            let range = response
                .headers()
                .get("Content-Range")
                .and_then(|s| s.to_str().ok())
                .context("Не указан диапазон загрузки")?;
            let (start, limit) = range
                .strip_prefix("bytes ")
                .and_then(|s| s.split_once('/'))
                .context("Неверный диапазон загрузки")?;
            let start = start
                .split_once('-')
                .context("Неверное начало диапазона")?
                .0
                .parse::<u64>()?;
            ensure!(
                start == offset,
                "Сервер вернул чужой диапазон"
            );
            total = Some(limit.parse::<u64>()?);
        } else {
            offset = 0;
            total = response.content_length();
        }
        const MAX: u64 = 8 * 1024 * 1024 * 1024;
        ensure!(
            total.is_none_or(|n| n <= MAX),
            "Модель больше 8 ГиБ"
        );
        if let Some(total) = total {
            ensure!(
                fs2::available_space(&root)?
                    > total.saturating_sub(offset)
                        + 64 * 1024 * 1024,
                "Недостаточно места для модели"
            );
        }
        let mut file = tokio::fs::OpenOptions::new()
            .create(true)
            .write(true)
            .append(offset > 0)
            .truncate(offset == 0)
            .open(&part)
            .await?;
        let mut stream = response.bytes_stream();
        use tokio::io::AsyncWriteExt;
        let mut last = std::time::Instant::now();
        loop {
            let chunk = tokio::select! { _=token.cancelled()=>anyhow::bail!("Пауза"), chunk=tokio::time::timeout(std::time::Duration::from_secs(60),stream.next())=>chunk.context("Соединение прервано. Можно продолжить загрузку")? };
            let Some(chunk) = chunk else {
                break;
            };
            let chunk = chunk?;
            ensure!(
                offset + chunk.len() as u64 <= MAX,
                "Модель больше 8 ГиБ"
            );
            file.write_all(&chunk).await?;
            offset += chunk.len() as u64;
            if last.elapsed().as_millis() > 200 {
                notify(
                    spec.id,
                    "downloading",
                    offset,
                    total,
                    String::new(),
                );
                last = std::time::Instant::now();
            }
        }
        file.sync_all().await?;
    }
    ensure!(
        total.is_none_or(|n| n == offset),
        "Загрузка оборвалась. Продолжите её"
    );
    notify(
        spec.id,
        "verifying",
        offset,
        total,
        String::new(),
    );
    let verified_part = part.clone();
    let verify_token = token.clone();
    let digest = super::runtime::blocking(move || {
        digest_file(&verified_part, &verify_token)
    })
    .await?;
    if digest != expected_digest {
        let _ = std::fs::remove_file(&part);
        anyhow::bail!(
            "SHA-256 не совпадает. Повреждённая модель удалена"
        );
    }
    ensure!(!token.is_cancelled(), "Пауза");
    std::fs::rename(&part, root.join(spec.filename))?;
    notify(
        spec.id,
        "installed",
        offset,
        total,
        String::new(),
    );
    Ok(())
}
/// Копирует оригинальный файл и проверяет его до атомарной установки.
pub fn import(spec: Model, source: &Path) -> Result<()> {
    let root = super::paths::models_dir()?;
    let _lease = lock(&root, spec)?;
    ensure!(source.is_file(), "Файл модели не найден");
    ensure!(
        fs2::available_space(&root)?
            > source.metadata()?.len() + 64 * 1024 * 1024,
        "Недостаточно места"
    );
    let temporary =
        root.join(format!("{}.importing", spec.filename));
    let result = (|| -> Result<()> {
        std::fs::copy(source, &temporary)?;
        ensure!(
            digest_file(
                &temporary,
                &CancellationToken::new()
            )? == super::model_updates::source(spec)?.1,
            "SHA-256 модели не совпадает"
        );
        std::fs::rename(
            &temporary,
            root.join(spec.filename),
        )?;
        Ok(())
    })();
    if result.is_err() {
        let _ = std::fs::remove_file(temporary);
    } else {
        let total =
            root.join(spec.filename).metadata()?.len();
        notify(
            spec.id,
            "installed",
            total,
            Some(total),
            String::new(),
        );
    }
    result
}
/// Принимает уже проверенный поток импорта, не создавая вторую гигабайтную копию.
pub(crate) fn install_staged(
    spec: Model,
    file: tempfile::NamedTempFile,
) -> Result<()> {
    let root = super::paths::models_dir()?;
    let _lease = lock(&root, spec)?;
    file.persist(root.join(spec.filename))
        .map_err(|e| e.error)?;
    let size = root.join(spec.filename).metadata()?.len();
    notify(
        spec.id,
        "installed",
        size,
        Some(size),
        String::new(),
    );
    Ok(())
}
/// Сохраняет явный выбор установленной локальной модели.
pub fn select(store: &Store, id: &str) -> Result<String> {
    let spec = model(id)?;
    installed_path(spec)?;
    ensure!(
        super::litert::available(),
        "LiteRT не включён в сборку"
    );
    store.with(|db| {
        db.set_setting("chat_model", spec.filename)?;
        db.set_setting("chat_provider", "local")?;
        Ok(())
    })?;
    Ok(spec.name.into())
}
/// Выгружает модель и удаляет только файлы выбранных весов.
pub fn remove(id: &str) -> Result<()> {
    let spec = model(id)?;
    super::litert::unload()?;
    let root = super::paths::models_dir()?;
    let _lease = lock(&root, spec)?;
    for path in [
        root.join(spec.filename),
        root.join(format!("{}.part", spec.filename)),
    ] {
        if path.is_file() {
            std::fs::remove_file(path)?;
        }
    }
    jobs()
        .lock()
        .map_err(|_| anyhow::anyhow!("Ошибка загрузчика"))?
        .remove(spec.id);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    /// Проверяет Range-продолжение и SHA-256 до публикации файла.
    #[tokio::test]
    async fn resume_checks_range_and_hash_before_publishing()
     {
        let directory = tempfile::tempdir().unwrap();
        let payload = b"verified-model-payload";
        let server =
            tokio::net::TcpListener::bind("127.0.0.1:0")
                .await
                .unwrap();
        let address = server.local_addr().unwrap();
        let worker = tokio::spawn(async move {
            let (mut stream, _) =
                server.accept().await.unwrap();
            let mut header = Vec::new();
            let mut bytes = [0; 1024];
            while !header
                .windows(4)
                .any(|w| w == b"\r\n\r\n")
            {
                let n =
                    stream.read(&mut bytes).await.unwrap();
                assert!(n > 0);
                header.extend_from_slice(&bytes[..n]);
            }
            assert!(
                String::from_utf8_lossy(&header)
                    .to_lowercase()
                    .contains("range: bytes=8-")
            );
            let tail = &payload[8..];
            let response = format!(
                "HTTP/1.1 206 Partial Content\r\nContent-Range: bytes 8-{}/{}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
                payload.len() - 1,
                payload.len(),
                tail.len()
            );
            stream
                .write_all(response.as_bytes())
                .await
                .unwrap();
            stream.write_all(tail).await.unwrap();
        });
        let spec = Model {
            id: "test-resume",
            name: "test",
            filename: "test.litertlm",
            size: "test",
            url: Box::leak(
                format!("http://{address}/model")
                    .into_boxed_str(),
            ),
            sha256: Box::leak(
                hex::encode(Sha256::digest(payload))
                    .into_boxed_str(),
            ),
        };
        std::fs::write(
            directory.path().join("test.litertlm.part"),
            &payload[..8],
        )
        .unwrap();
        download_to(
            spec,
            CancellationToken::new(),
            directory.path().into(),
        )
        .await
        .unwrap();
        worker.await.unwrap();
        assert_eq!(
            std::fs::read(
                directory.path().join("test.litertlm")
            )
            .unwrap(),
            payload
        );
        assert!(
            !directory
                .path()
                .join("test.litertlm.part")
                .exists()
        );
    }
    /// Запрещает выбор недокачанных или повреждённых весов.
    #[tokio::test]
    async fn incomplete_or_corrupt_download_cannot_be_selected()
     {
        // При повреждённом обновлении прежние рабочие веса должны сохраниться.
        for preserve_existing in [false, true] {
            let directory = tempfile::tempdir().unwrap();
            let payload = b"bad model";
            let listener = tokio::net::TcpListener::bind(
                "127.0.0.1:0",
            )
            .await
            .unwrap();
            let address = listener.local_addr().unwrap();
            let server = tokio::spawn(async move {
                let (mut stream, _) =
                    listener.accept().await.unwrap();
                let mut bytes = [0; 2048];
                let _ = stream.read(&mut bytes).await;
                stream
                .write_all(
                    format!(
                        "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
                        payload.len()
                    )
                    .as_bytes(),
                )
                .await
                .unwrap();
                stream.write_all(payload).await.unwrap();
            });
            let spec = Model {
                id: "test-corrupt",
                name: "test",
                filename: "test.litertlm",
                size: "test",
                url: Box::leak(
                    format!("http://{address}/model")
                        .into_boxed_str(),
                ),
                sha256: "0000000000000000000000000000000000000000000000000000000000000000",
            };
            if preserve_existing {
                std::fs::write(
                    directory.path().join(spec.filename),
                    b"previous verified model",
                )
                .unwrap();
            }
            assert!(
                download_to(
                    spec,
                    CancellationToken::new(),
                    directory.path().into()
                )
                .await
                .unwrap_err()
                .to_string()
                .contains("SHA-256")
            );
            server.await.unwrap();
            if preserve_existing {
                assert_eq!(
                    std::fs::read(
                        directory
                            .path()
                            .join(spec.filename)
                    )
                    .unwrap(),
                    b"previous verified model"
                );
            } else {
                assert!(
                    !directory
                        .path()
                        .join(spec.filename)
                        .exists()
                );
            }
            assert!(
                !directory
                    .path()
                    .join("test.litertlm.part")
                    .exists()
            );
        }
    }
}
