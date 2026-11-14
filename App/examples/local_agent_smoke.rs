// Описание: Настоящая Gemma выполняет задачу инструментами в отдельной временной папке.
use anyhow::Result;
use xopilot::services::{
    agent, db::Store, generation::Configuration,
    workspaces::Workspace,
};

/// Проверяет изменение и повторное чтение настоящего файла без доступа к личной истории.
fn main() -> Result<()> {
    let model =
        std::env::args().nth(1).ok_or_else(|| {
            anyhow::anyhow!("Укажите .litertlm")
        })?;
    let project = tempfile::tempdir()?;
    std::fs::write(
        project.path().join("example.txt"),
        "old",
    )?;
    let store =
        Store::new(advanced_xopilot::db::Database::open(
            ":memory:",
            &"a".repeat(64),
        )?);
    let chat = store.with(|db| {
        Ok(db.create_chat("Проверка локального агента")?)
    })?;
    let messages = vec![
        serde_json::json!({"role": "system", "content": "You are a helpful assistant."}),
        serde_json::json!({
            "role": "user",
            "content": "Read example.txt. Replace all contents with the literal 3-character string \"new\" (no newline). Use write_project_file. Read again to verify. Do not run commands."
        }),
    ];
    xopilot::services::runtime::runtime().block_on(async {
        let (events, mut receiver) = tokio::sync::mpsc::unbounded_channel();
        let progress = tokio::spawn(async move {
            while let Some(event) = receiver.recv().await {
                match event {
                    agent::Event::Progress(text) => println!("AGENT_PROGRESS {text}"),
                    agent::Event::Approval(request) => request.answer(false),
                    agent::Event::ToolResult { tool, output } => {
                        println!("AGENT_RESULT {tool}: {output}");
                    }
                    _ => {}
                }
            }
        });
        let context = agent::ContextData {
            store,
            chat,
            workspace: Workspace {
                name: "Smoke".into(),
                folder: project.path().to_string_lossy().into(),
                ..Default::default()
            },
            settings: agent::Settings {
                enabled: true,
                automatic: true,
                max_steps: 8,
                ..Default::default()
            },
            control: Default::default(),
            events,
        };
        let (tx, _rx) = tokio::sync::mpsc::unbounded_channel();
        let reply = agent::run(
            Configuration::Local {
                path: model.into(),
                backend: "cpu".into(),
            },
            messages,
            tokio_util::sync::CancellationToken::new(),
            tx,
            context,
        )
        .await?;
        progress.await?;
        let saved = std::fs::read_to_string(project.path().join("example.txt"))?;
        println!("LOCAL_AGENT_REPLY {reply}");
        println!("LOCAL_AGENT_FILE {saved:?}");
        anyhow::ensure!(saved == "new", "Агент не выполнил запись");
        Ok::<_, anyhow::Error>(())
    })?;
    xopilot::services::litert::unload()?;
    Ok(())
}
