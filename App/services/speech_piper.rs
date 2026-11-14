// Piper запускается отдельным нативным процессом. Python и pip для работы не нужны.
// Движок и голос хранятся в данных приложения, загрузки проверяются SHA-256.
use anyhow::{Context, Result, ensure};
use sha2::{Digest, Sha256};
use std::{
    path::{Path, PathBuf},
    sync::OnceLock,
};
use tokio::{io::AsyncWriteExt, sync::Mutex};
use tokio_util::sync::CancellationToken;
const VOICE_SHA: &str = "72a5f88e0b20928064eb45d88e1daa21f8af62d18613580d32cbb4aed48dcf7f";
const CONFIG_SHA: &str = "706a4fb17bc304abd07809b552deae615e64dcbffbfbd09854ba37ca59e88117";
const COMMIT: &str =
    "2f358b6a560e3a913ebf509b2f3344f20b367f94";

/// Загружаю ограниченный файл во временное имя и публикую только после проверки.
async fn download(
    url: &str,
    path: &Path,
    hash: &str,
    limit: u64,
    token: &CancellationToken,
) -> Result<()> {
    if path.is_file() {
        ensure!(
            path.metadata()?.len() <= limit,
            "Слишком большой файл в кеше голоса"
        );
        let cached = path.to_path_buf();
        let cancel = token.clone();
        let digest = super::runtime::blocking(move || {
            super::model_installer::digest_file(
                &cached, &cancel,
            )
        })
        .await?;
        if digest == hash {
            return Ok(());
        }
        std::fs::remove_file(path)?;
    }
    let client = super::http_client::builder()?
        .timeout(std::time::Duration::from_secs(1200))
        .build()?;
    let mut response = tokio::select! {_=token.cancelled()=>anyhow::bail!("Загрузка голоса остановлена"),r=client.get(url).send()=>r?.error_for_status()?};
    let total = response.content_length();
    ensure!(
        total.is_none_or(|n| n <= limit),
        "Слишком большой файл голоса"
    );
    let parent =
        path.parent().context("Нет каталога голоса")?;
    let temporary =
        tempfile::NamedTempFile::new_in(parent)?;
    let mut file =
        tokio::fs::File::from_std(temporary.reopen()?);
    let mut digest = Sha256::new();
    let mut size = 0;
    loop {
        let chunk = tokio::select! {_=token.cancelled()=>anyhow::bail!("Загрузка голоса остановлена"),r=response.chunk()=>r?};
        let Some(chunk) = chunk else { break };
        size += chunk.len() as u64;
        ensure!(
            size <= limit,
            "Слишком большой файл голоса"
        );
        digest.update(&chunk);
        file.write_all(&chunk).await?;
        let phase = match path
            .file_name()
            .and_then(|name| name.to_str())
        {
            Some("runtime.tar.gz") => {
                "Загрузка движка речи"
            }
            Some("voice.onnx") => "Загрузка голоса Piper",
            _ => "Настройка голоса",
        };
        super::speech::report(phase, size, total);
    }
    file.sync_all().await?;
    drop(file);
    ensure!(
        hex::encode(digest.finalize()) == hash,
        "SHA-256 голоса не совпадает"
    );
    temporary.persist(path).map_err(|e| e.error)?;
    Ok(())
}

/// Распаковываю только относительные пути официального архива, включая безопасные ссылки библиотек.
fn extract(archive: &Path, root: &Path) -> Result<()> {
    let mut archive =
        tar::Archive::new(flate2::read::GzDecoder::new(
            std::fs::File::open(archive)?,
        ));
    for entry in archive.entries()? {
        let mut entry = entry?;
        ensure!(
            entry.path()?.components().all(|p| matches!(
                p,
                std::path::Component::Normal(_)
            )),
            "Неверный путь Piper"
        );
        if let Some(link) = entry.link_name()? {
            ensure!(
                link.components().all(|p| matches!(
                    p,
                    std::path::Component::Normal(_)
                )),
                "Неверная ссылка Piper"
            );
        }
        ensure!(
            entry.unpack_in(root)?,
            "Не удалось распаковать Piper"
        );
    }
    Ok(())
}

/// Подготавливаю голос один раз, параллельные запросы не распаковывают общий каталог одновременно.
async fn prepare(
    token: &CancellationToken,
    voice: bool,
) -> Result<PathBuf> {
    static INSTALL: OnceLock<Mutex<()>> = OnceLock::new();
    let _guard = tokio::select! {_=token.cancelled()=>anyhow::bail!("Озвучивание остановлено"),g=INSTALL.get_or_init(Default::default).lock()=>g};
    let root = super::paths::base_data_dir()?
        .join("speech/piper-2023.11.14-2");
    std::fs::create_dir_all(&root)?;
    std::fs::write(
        root.join("NOTICE.md"),
        include_str!("../assets/voice/PIPER_NOTICE.md"),
    )?;
    let lease = std::fs::OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(root.join("prepare.lock"))?;
    fs2::FileExt::try_lock_exclusive(&lease).context(
        "Голос подготавливается в другом окне Xopilot",
    )?;
    ensure!(
        cfg!(any(
            target_arch = "x86_64",
            target_arch = "aarch64"
        )),
        "Piper поддерживается на Linux x86_64 и ARM64"
    );
    let (platform, hash) = if cfg!(target_arch = "aarch64")
    {
        (
            "aarch64",
            "fea0fd2d87c54dbc7078d0f878289f404bd4d6eea6e7444a77835d1537ab88eb",
        )
    } else {
        (
            "x86_64",
            "a50cb45f355b7af1f6d758c1b360717877ba0a398cc8cbe6d2a7a3a26e225992",
        )
    };
    let archive = root.join("runtime.tar.gz");
    if !root.join("ready").is_file() {
        download(&format!("https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_{platform}.tar.gz"),&archive,hash,50*1024*1024,token).await?;
        let work = root.clone();
        super::runtime::blocking(move || {
            extract(&archive, &work)
        })
        .await?;
        std::fs::write(
            root.join("ready"),
            b"piper native runtime",
        )?;
    }
    use std::os::unix::fs::PermissionsExt;
    std::fs::set_permissions(
        root.join("piper/espeak-ng"),
        std::fs::Permissions::from_mode(0o755),
    )?;
    if !voice {
        return Ok(root);
    }
    let prefix = format!(
        "https://huggingface.co/rhasspy/piper-voices/resolve/{COMMIT}/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.onnx"
    );
    download(
        &prefix,
        &root.join("voice.onnx"),
        VOICE_SHA,
        100 * 1024 * 1024,
        token,
    )
    .await?;
    download(
        &format!("{prefix}.json"),
        &root.join("voice.onnx.json"),
        CONFIG_SHA,
        64 * 1024,
        token,
    )
    .await?;
    Ok(root)
}

/// Синтезирую PCM16 22050 Гц без воспроизведения. Этот путь проверяется отдельным smoke-тестом.
pub async fn synthesize(
    text: String,
    token: CancellationToken,
) -> Result<Vec<f32>> {
    ensure!(
        text.chars().count() <= 1000,
        "Слишком длинная фраза"
    );
    let root = prepare(&token, false).await?;
    let neural = root.join("voice-enabled").is_file();
    super::speech::report("Подготовка речи", 0, None);
    let runtime = root.join("piper");
    let mut command =
        tokio::process::Command::new(runtime.join(
            if neural { "piper" } else { "espeak-ng" },
        ));
    if neural {
        command
            .arg("--model")
            .arg(root.join("voice.onnx"))
            .arg("--output_raw");
    } else {
        command
            .arg(format!("--path={}", runtime.display()))
            .arg("--stdout")
            .arg("-v")
            .arg("ru")
            .arg("--stdin");
    }
    let mut child = command
        .env("LD_LIBRARY_PATH", &runtime)
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::null())
        .kill_on_drop(true)
        .spawn()
        .context("Не удалось запустить нативный голос")?;
    let mut input =
        child.stdin.take().context("Нет входа Piper")?;
    input
        .write_all(
            format!("{}\n", text.replace('\n', " "))
                .as_bytes(),
        )
        .await?;
    drop(input);
    let output = tokio::select! {_=token.cancelled()=>anyhow::bail!("Озвучивание остановлено"),r=tokio::time::timeout(std::time::Duration::from_secs(60),child.wait_with_output())=>r.context("Piper не ответил")??};
    ensure!(
        output.status.success(),
        "Ошибка синтеза Piper"
    );
    let pcm = if neural {
        output.stdout.as_slice()
    } else {
        wav_pcm(&output.stdout)?
    };
    ensure!(
        !pcm.is_empty()
            && pcm.len() <= 22050 * 2 * 60
            && pcm.len() % 2 == 0,
        "Неверный PCM от голоса"
    );
    Ok(pcm
        .as_chunks::<2>()
        .0
        .iter()
        .map(|b| i16::from_le_bytes(*b) as f32 / 32768.)
        .collect())
}

/// Сохраняю явный выбор дополнительного голоса, базовый eSpeak остаётся доступен.
pub async fn enable(
    token: CancellationToken,
) -> Result<()> {
    let root = prepare(&token, true).await?;
    ensure!(
        !token.is_cancelled(),
        "Загрузка голоса остановлена"
    );
    std::fs::write(
        root.join("voice-enabled"),
        b"Ruslan CC-BY-NC-SA-4.0",
    )?;
    if token.is_cancelled() {
        let _ = std::fs::remove_file(
            root.join("voice-enabled"),
        );
        anyhow::bail!("Выбор голоса отменён");
    }
    Ok(())
}
/// Переключаюсь на базовый голос без повторного скачивания и удаления файлов.
pub fn disable() -> Result<()> {
    let root = super::paths::base_data_dir()?
        .join("speech/piper-2023.11.14-2");
    let path = root.join("voice-enabled");
    if path.exists() {
        std::fs::remove_file(path)?;
    }
    Ok(())
}

/// eSpeak пишет потоковый WAV с заранее неизвестным размером data. Читаю до фактического EOF.
fn wav_pcm(bytes: &[u8]) -> Result<&[u8]> {
    ensure!(
        bytes.len() >= 12
            && &bytes[..4] == b"RIFF"
            && &bytes[8..12] == b"WAVE",
        "Неверный WAV от eSpeak"
    );
    let mut offset = 12;
    let mut format = false;
    while offset + 8 <= bytes.len() {
        let size = u32::from_le_bytes(
            bytes[offset + 4..offset + 8].try_into()?,
        ) as usize;
        let start = offset + 8;
        if &bytes[offset..offset + 4] == b"data" {
            ensure!(format, "Нет PCM-формата WAV");
            return Ok(&bytes[start
                ..start + size.min(bytes.len() - start)]);
        }
        ensure!(
            size <= bytes.len() - start,
            "Оборван WAV-чанк"
        );
        if &bytes[offset..offset + 4] == b"fmt " {
            ensure!(size >= 16, "Оборван формат WAV");
            format = u16::from_le_bytes(
                bytes[start..start + 2].try_into()?,
            ) == 1
                && u16::from_le_bytes(
                    bytes[start + 2..start + 4]
                        .try_into()?,
                ) == 1
                && u32::from_le_bytes(
                    bytes[start + 4..start + 8]
                        .try_into()?,
                ) == 22050
                && u16::from_le_bytes(
                    bytes[start + 14..start + 16]
                        .try_into()?,
                ) == 16;
        }
        offset = start + size + (size % 2);
    }
    anyhow::bail!("Нет звука в WAV")
}

#[cfg(test)]
mod tests {
    use super::*;
    /// Потоковый размер data может быть неизвестным, фактический PCM всё равно ограничен EOF.
    #[test]
    fn reads_streaming_wav_and_rejects_wrong_format() {
        let mut bytes = Vec::new();
        bytes.extend_from_slice(b"RIFF");
        bytes.extend_from_slice(&u32::MAX.to_le_bytes());
        bytes.extend_from_slice(b"WAVEfmt ");
        bytes.extend_from_slice(&16u32.to_le_bytes());
        bytes.extend_from_slice(&1u16.to_le_bytes());
        bytes.extend_from_slice(&1u16.to_le_bytes());
        bytes.extend_from_slice(&22050u32.to_le_bytes());
        bytes.extend_from_slice(&44100u32.to_le_bytes());
        bytes.extend_from_slice(&2u16.to_le_bytes());
        bytes.extend_from_slice(&16u16.to_le_bytes());
        bytes.extend_from_slice(b"data");
        bytes.extend_from_slice(&u32::MAX.to_le_bytes());
        bytes.extend_from_slice(&[0, 0, 1, 0]);
        assert_eq!(wav_pcm(&bytes).unwrap(), &[0, 0, 1, 0]);
        bytes[22] = 2;
        assert!(wav_pcm(&bytes).is_err());
        assert!(wav_pcm(b"RIFF").is_err());
    }
}
