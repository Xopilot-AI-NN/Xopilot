// Описание: Диагностический отчёт по запросу пользователя без переписок и секретов.
use anyhow::Result;
use serde_json::json;
use std::{io::Write, path::PathBuf};

/// Формирует технический снимок. Содержимое БД, пути пользователя и ключи не читаются.
pub fn snapshot() -> serde_json::Value {
    json!({
        "application": "Xopilot",
        "version": env!("CARGO_PKG_VERSION"),
        "os": std::env::consts::OS,
        "architecture": std::env::consts::ARCH,
        "litert_bundled": super::litert::available(),
        "format_version": 1
    })
}

/// Записывает ZIP атомарно в exports. Отчёт создаётся только явным действием в UI.
pub fn create() -> Result<PathBuf> {
    let root =
        super::paths::app_data_dir()?.join("exports");
    std::fs::create_dir_all(&root)?;
    let output = root.join(format!(
        "diagnostics-{}.zip",
        uuid::Uuid::new_v4()
    ));
    let mut temporary =
        tempfile::NamedTempFile::new_in(&root)?;
    {
        let mut archive =
            zip::ZipWriter::new(temporary.as_file_mut());
        archive.start_file(
            "diagnostics.json",
            zip::write::SimpleFileOptions::default(),
        )?;
        archive.write_all(&serde_json::to_vec_pretty(
            &snapshot(),
        )?)?;
        archive.finish()?;
    }
    temporary.as_file().sync_all()?;
    temporary
        .persist(&output)
        .map_err(|error| error.error)?;
    Ok(output)
}
