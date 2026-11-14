// Проверка команды на настоящей локальной модели: пять исследований и одна загрузка весов.
use anyhow::Result;
use serde_json::json;
use tokio_util::sync::CancellationToken;
use xopilot::services::{
    agent::{self, Event},
    agent_modes::{self, Depth, Mode},
    canvases::{self, Document},
    db::Store,
    generation::Configuration,
};

#[tokio::main]
async fn main() -> Result<()> {
    let path =
        std::env::args().nth(1).ok_or_else(|| {
            anyhow::anyhow!("Укажите файл Gemma E2B")
        })?;
    let directory = tempfile::tempdir()?;
    let store =
        Store::new(advanced_xopilot::db::Database::open(
            directory.path().join("test.db"),
            "test-key",
        )?);
    let chat = store
        .with(|db| Ok(db.create_chat("Team smoke")?))?;
    for title in ["One", "Two"] {
        canvases::save_document(
            &store,
            Document {
                // Документы принадлежат проверяемому чату: чужие Canvas агенту недоступны.
                chat_id: Some(chat),
                title: title.into(),
                kind: "text".into(),
                ..Default::default()
            },
        )?;
    }
    println!(
        "TEAM_DOCUMENTS {}",
        canvases::list_documents(&store)?.len()
    );
    let token = CancellationToken::new();
    let timer = token.clone();
    let watchdog = tokio::spawn(async move {
        tokio::time::sleep(std::time::Duration::from_secs(
            180,
        ))
        .await;
        timer.cancel();
    });
    let (events, mut receiver) =
        tokio::sync::mpsc::unbounded_channel();
    let journal = tokio::spawn(async move {
        let (mut agents, mut tools) = (0, 0);
        while let Some(event) = receiver.recv().await {
            match event {
                Event::Deliberation {
                    title,
                    state,
                    ..
                } if state == "completed" => {
                    println!("TEAM_AGENT {title}");
                    agents += 1;
                }
                Event::ToolFinished {
                    id, output, ..
                } => println!("TEAM_RESULT {id} {output}"),
                Event::ToolStarted { id, tool, .. } => {
                    println!("TEAM_TOOL {id} {tool}");
                    tools += 1;
                }
                _ => {}
            }
        }
        (agents, tools)
    });
    let (updates, mut text) =
        tokio::sync::mpsc::unbounded_channel();
    let drain = tokio::spawn(async move {
        while text.recv().await.is_some() {}
    });
    // Все исследователи используют одну модель и документы текущего чата.
    let configuration = Configuration::Local {
        path: path.into(),
        backend: "cpu".into(),
    };
    let messages = vec![
        json!({"role":"system","content":"You are Xopilot. Complete the user's task accurately."}),
        json!({"role":"user","content":"Count local Canvas documents using list_canvases. Reply with just the number. No internet search."}),
    ];
    let context = agent::ContextData {
        store: store.clone(),
        chat,
        workspace: Default::default(),
        settings: agent::Settings {
            enabled: true,
            mode: Mode::Multi,
            depth: Depth::Light,
            ..Default::default()
        },
        control: Default::default(),
        events,
    };
    let result = agent_modes::run(
        configuration,
        messages,
        token,
        updates,
        context,
    )
    .await;
    watchdog.abort();
    let _ = drain.await;
    let (agents, tools) = journal.await?;
    let answer = result?;
    let stats = xopilot::services::litert::context_stats()?;
    println!("TEAM_ANSWER {answer}");
    println!(
        "TEAM_STATS agents={agents} tools={tools} engine_loads={} reused={}",
        stats.engine_loads, stats.reused
    );
    anyhow::ensure!(
        agents == 5,
        "Не завершились пять исследований"
    );
    anyhow::ensure!(
        tools >= 5,
        "Исследователи не прочитали документы"
    );
    anyhow::ensure!(
        stats.engine_loads == 1,
        "Веса загружались повторно"
    );
    anyhow::ensure!(
        stats.reused > 0,
        "KV не использовался между шагами"
    );
    let numbers = answer
        .split(|c: char| !c.is_ascii_digit())
        .filter(|s| !s.is_empty())
        .collect::<Vec<_>>();
    anyhow::ensure!(
        numbers == ["2"],
        "Неверное число документов"
    );
    anyhow::ensure!(
        canvases::list_documents(&store)?.len() == 2,
        "Исследователи изменили документы"
    );
    Ok(())
}
