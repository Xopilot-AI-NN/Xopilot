// Описание: Проверка импорта настоящего файла в отдельно заданный каталог.
fn main() -> anyhow::Result<()> {
    anyhow::ensure!(
        std::env::var_os("XOPILOT_MODELS_DIR").is_some(),
        "Укажите отдельный XOPILOT_MODELS_DIR"
    );
    let source =
        std::env::args().nth(1).ok_or_else(|| {
            anyhow::anyhow!("Укажите файл модели")
        })?;
    let spec =
        xopilot::services::model_installer::MODELS[0];
    xopilot::services::model_import::import_file(
        std::path::Path::new(&source),
    )?;
    println!(
        "IMPORTED {}",
        xopilot::services::model_installer::installed_path(
            spec
        )?
        .display()
    );
    Ok(())
}
