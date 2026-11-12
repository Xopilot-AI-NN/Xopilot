// Описание: Настоящая локальная генерация без WebView, сети и пользовательской базы.
fn main() -> anyhow::Result<()> {
    let path =
        std::env::args().nth(1).ok_or_else(|| {
            anyhow::anyhow!("Укажите путь к .litertlm")
        })?;
    let custom = std::env::args().nth(2);
    let (tx, _rx) = tokio::sync::mpsc::unbounded_channel();
    let answer = xopilot::services::litert::generate(
        path.into(),
        "cpu".into(),
        vec![
            serde_json::json!({"role":"system","content":"You are a helpful assistant. Answer briefly."}),
            serde_json::json!({"role":"user","content":custom.as_deref().unwrap_or("What is 2 + 2? Reply with just the number.")}),
        ],
        tokio_util::sync::CancellationToken::new(),
        tx,
        64,
    )?;
    println!("LOCAL_MODEL_REPLY {answer}");
    anyhow::ensure!(
        custom.is_some() || answer.trim() == "4",
        "Ожидался числовой ответ, получено: {answer}"
    );
    xopilot::services::litert::unload()?;
    Ok(())
}
