// Проверка синтеза и распознавания подготовленной речи. Микрофон и динамики не включаются.
#[cfg(all(target_os = "linux", feature = "desktop"))]
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    use tokio_util::sync::CancellationToken;
    use xopilot::services::{
        generation::Configuration, speech_piper, voice,
    };
    anyhow::ensure!(
        std::env::var_os("XOPILOT_DATA_DIR").is_some(),
        "Нужен отдельный XOPILOT_DATA_DIR для теста"
    );
    let samples = speech_piper::synthesize(
        "Привет. Это проверка голоса.".into(),
        CancellationToken::new(),
    )
    .await?;
    anyhow::ensure!(
        samples.len() > 22050
            && samples.iter().any(|v| v.abs() > 0.01),
        "Нет синтезированной речи"
    );
    let bytes = voice::encode_wav(&samples, 22050);
    let output = std::path::PathBuf::from(
        std::env::var_os("XOPILOT_DATA_DIR").unwrap(),
    )
    .join("speech-fixture.wav");
    std::fs::write(&output, &bytes)?;
    println!(
        "SPEECH_SYNTHESIZED seconds={:.2} wav={}",
        samples.len() as f64 / 22050.,
        output.display()
    );
    if let Some(path) =
        std::env::var_os("XOPILOT_TEST_MODEL")
    {
        let text = voice::transcribe(
            Configuration::Local {
                path: path.into(),
                backend: "cpu".into(),
            },
            bytes,
            CancellationToken::new(),
        )
        .await?;
        println!("SPEECH_TRANSCRIPT {text}");
        anyhow::ensure!(
            text.to_lowercase().contains("проверка"),
            "Проверочная фраза не распознана"
        );
    }
    Ok(())
}
#[cfg(not(all(target_os = "linux", feature = "desktop")))]
fn main() {
    eprintln!(
        "Нативный синтез проверяется на Linux desktop"
    );
}
