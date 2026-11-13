// Описание: Проверка настоящих кодеков WebView, кеша и мультимодального контекста.
// cargo run -p xopilot --example media_smoke -- /путь/звук.wav /путь/видео.mp4
// XOPILOT_TEST_MODEL дополнительно включает настоящий локальный инференс.
use anyhow::{Result, ensure};
use dioxus::prelude::*;
use tokio_util::sync::CancellationToken;
use xopilot::services::{
    api_chat, db::Store, generation, media, runtime,
};

fn main() {
    dioxus::launch(probe);
}

/// Запускает проверку после создания WebView, затем закрывает тестовое окно.
#[component]
fn probe() -> Element {
    use_future(|| async {
        let result = check().await;
        match result {
            Ok(()) => std::process::exit(0),
            Err(error) => {
                eprintln!("MEDIA_ERROR {error:#}");
                std::process::exit(1);
            }
        }
    });
    rsx! { p { "Проверка обработки медиа…" } }
}

/// Использует отдельную SQLCipher в памяти и сохраняет исходные вложения.
async fn check() -> Result<()> {
    let files: Vec<_> = std::env::args()
        .skip(1)
        .map(|path| {
            let name = std::path::Path::new(&path)
                .file_name()
                .unwrap()
                .to_string_lossy()
                .into_owned();
            (name, path)
        })
        .collect();
    ensure!(!files.is_empty(), "Укажите аудио или видео");
    let store =
        Store::new(advanced_xopilot::db::Database::open(
            ":memory:",
            &"a".repeat(64),
        )?);
    let history = store.with(|db| {
        let chat = db.create_chat("Media smoke")?;
        db.add_message_full(chat, "user", "Describe what you see and hear in these attachments. Do not invent speech if the audio is only a tone.", None, None, &files, None)?;
        Ok(db.get_messages(chat)?)
    })?;
    let token = CancellationToken::new();
    media::prepare_history(&history, &token).await?;
    let messages = api_chat::build_messages(&history, "");
    let content = messages[1]["content"]
        .as_array()
        .ok_or_else(|| {
            anyhow::anyhow!(
                "Нет мультимодальных частей: {}",
                messages[1]["content"]
            )
        })?;
    let text =
        content[0]["text"].as_str().unwrap_or_default();
    ensure!(!text.contains("Ошибка чтения"), "{text}");
    let images = content
        .iter()
        .filter(|part| part["type"] == "image_url")
        .count();
    let audio = content
        .iter()
        .filter(|part| part["type"] == "input_audio")
        .count();
    ensure!(
        images + audio > 0,
        "Нет подготовленных кадров или аудио"
    );
    // Повторное чтение истории использует готовые файлы, а не декодирует их заново.
    media::prepare_history(&history, &token).await?;
    ensure!(
        messages == api_chat::build_messages(&history, ""),
        "Изменился сохранённый контекст"
    );
    println!(
        "MEDIA_OK images={images} audio={audio} files={}",
        files.len()
    );
    if let Some(path) =
        std::env::var_os("XOPILOT_TEST_MODEL")
    {
        let (updates, mut receiver) =
            tokio::sync::mpsc::unbounded_channel();
        let drain = runtime::runtime().spawn(async move {
            while receiver.recv().await.is_some() {}
        });
        let answer =
            runtime::background(generation::reply(
                generation::Configuration::Local {
                    path: path.into(),
                    backend: "cpu".into(),
                },
                messages,
                token,
                updates,
            ))
            .await?;
        drain.await?;
        ensure!(
            !answer.trim().is_empty(),
            "Модель вернула пустой ответ"
        );
        println!("MEDIA_ANSWER {answer}");
    }
    Ok(())
}
