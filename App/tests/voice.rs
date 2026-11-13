// Проверка диктовки на подготовленной речи без доступа к микрофону пользователя.
use tokio_util::sync::CancellationToken;
use xopilot::services::{generation::Configuration, voice};

#[tokio::test]
#[ignore = "Нужны XOPILOT_TEST_MODEL и XOPILOT_TEST_AUDIO (WAV mono PCM16 16 кГц)"]
async fn local_dictation_returns_the_spoken_words() {
    let path =
        std::env::var_os("XOPILOT_TEST_MODEL").unwrap();
    let bytes = std::fs::read(
        std::env::var_os("XOPILOT_TEST_AUDIO").unwrap(),
    )
    .unwrap();
    let text = voice::transcribe(
        Configuration::Local {
            path: path.into(),
            backend: "cpu".into(),
        },
        bytes,
        CancellationToken::new(),
    )
    .await
    .unwrap();
    println!("DICTATION {text}");
    assert!(text.to_lowercase().contains("roses are red"));
    assert!(
        text.to_lowercase().contains("violets are blue")
    );
}
