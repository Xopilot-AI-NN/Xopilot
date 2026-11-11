// Описание: Настоящие разговоры Gemma о Canvas, проверка результата и единственной загрузки весов.
use anyhow::Result;
use xopilot::services::{self, agent, db::Store, generation::Configuration};

/// Повторяет три последовательных вопроса через тот же путь контекста, что и интерфейс.
fn main() -> Result<()> {
    let path = std::env::args()
        .nth(1)
        .ok_or_else(|| anyhow::anyhow!("Укажите .litertlm"))?;
    let store = Store::new(advanced_xopilot::db::Database::open(
        ":memory:",
        &"d".repeat(64),
    )?);
    services::profile::ensure_local(&store)?;
    let chat = store.with(|db| Ok(db.create_chat("Canvas smoke")?))?;
    let questions = [
        "Привет!",
        "Сколько у меня канвасов? Проверь список.",
        r#"Создай канвас с содержимым "Привет мир"."#,
        r#"Создай файл с содержимым "Привет!" в ~/Desktop."#,
        "создай canvas",
        "тоже самое",
    ];
    services::runtime::runtime().block_on(async {
        let config = Configuration::Local {
            path: path.into(),
            backend: "cpu".into(),
        };
        for question in questions {
            store.with(|db| {
                db.add_message_full(chat, "user", question, None, None, &[], None)?;
                Ok(())
            })?;
            let history = store.with(|db| Ok(db.get_messages(chat)?))?;
            let instructions = services::profile::instructions(&store)?;
            let messages = services::api_chat::build_messages(&history, &instructions);
            let (events, mut receiver) = tokio::sync::mpsc::unbounded_channel();
            let collector = tokio::spawn(async move {
                while let Some(event) = receiver.recv().await {
                    match event {
                        agent::Event::Approval(approval) => approval.answer(false),
                        agent::Event::ToolResult { tool, output } => {
                            println!("CANVAS_TOOL {tool} {output}");
                        }
                        _ => {}
                    }
                }
            });
            let context = agent::ContextData {
                store: store.clone(),
                chat,
                workspace: Default::default(),
                settings: agent::Settings {
                    enabled: true,
                    automatic: true,
                    max_steps: 8,
                },
                control: Default::default(),
                events,
            };
            let (tx, _rx) = tokio::sync::mpsc::unbounded_channel();
            let answer = agent::run(
                config.clone(),
                messages,
                tokio_util::sync::CancellationToken::new(),
                tx,
                context,
            )
            .await?;
            collector.await?;
            anyhow::ensure!(
                !answer.contains("\"tool\"")
                    && !answer.contains("final:")
                    && !answer.starts_with("final ")
                    && !answer.contains("\"arguments\""),
                "Служебный протокол попал в ответ: {answer}"
            );
            println!("CANVAS_REPLY {answer}");
            store.with(|db| {
                db.add_message_full(chat, "ai", &answer, None, None, &[], None)?;
                Ok(())
            })?;
        }
        let docs = services::canvases::list_documents(&store)?;
        anyhow::ensure!(
            docs.iter().any(|doc| !doc.title.is_empty()
                && doc.kind == "text"
                && doc.content.trim() == "Привет мир"),
            "Canvas не создан с запрошенным содержимым"
        );
        anyhow::ensure!(
            docs.iter()
                .any(|doc| doc.kind == "text" && doc.content == "Привет!"),
            "Агент потерял содержимое предыдущей просьбы при переходе к Canvas"
        );
        let stats = services::litert::context_stats()?;
        println!("CANVAS_CONTEXT {stats:?}");
        anyhow::ensure!(
            stats.engine_loads == 1,
            "Веса повторно загружались: {stats:?}"
        );
        anyhow::ensure!(
            stats.reused >= 2,
            "Готовый контекст не использован: {stats:?}"
        );
        Ok::<_, anyhow::Error>(())
    })?;
    services::litert::unload()?;
    Ok(())
}
