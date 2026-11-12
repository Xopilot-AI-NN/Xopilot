// Описание: Проверяем настоящий KV-кеш и его сброс на локальной модели, без сети.
use serde_json::json;
use xopilot::services::litert;
/// Запускает отдельный проверочный стенд без обращения к личной истории.
fn main() -> anyhow::Result<()> {
    let path =
        std::env::args().nth(1).ok_or_else(|| {
            anyhow::anyhow!("Укажите .litertlm")
        })?;
    let ask = |history| {
        let (tx, _rx) =
            tokio::sync::mpsc::unbounded_channel();
        litert::generate(
            path.clone().into(),
            "cpu".into(),
            history,
            tokio_util::sync::CancellationToken::new(),
            tx,
            64,
        )
    };
    let mut history = vec![
        json!({"role":"system","content":"Answer briefly. Remember facts in the conversation."}),
        json!({"role":"user","content":"My secret word is apricot. Reply only OK."}),
    ];
    let first = ask(history.clone())?;
    history
        .push(json!({"role":"assistant","content":first}));
    history.push(
        json!({"role":"user","content":"What is my secret word? Reply with just that word."}),
    );
    let second = ask(history.clone())?;
    let stats = litert::context_stats()?;
    anyhow::ensure!(
        second.to_lowercase().contains("apricot"),
        "Потеряна история: {second}"
    );
    anyhow::ensure!(
        stats.reused == 1
            && stats.rebuilt == 1
            && stats.tokens > 0,
        "Контекст не дополнен: {stats:?}"
    );
    history[1] = json!({"role":"user","content":"My secret word is plum. Reply only OK."});
    let edited = ask(history)?;
    let stats = litert::context_stats()?;
    anyhow::ensure!(
        edited.to_lowercase().contains("plum")
            && stats.rebuilt == 2,
        "Редактирование не пересобрало контекст: {stats:?}, {edited}"
    );
    litert::reset_context()?;
    ask(vec![
        json!({"role":"user","content":"What is 2+2? Reply with just the number."}),
    ])?;
    anyhow::ensure!(
        litert::context_stats()?.rebuilt == 3,
        "Смена чата не сбросила контекст"
    );
    println!(
        "CONTEXT_OK: дополнение, память разговора, правка истории и сброс чата"
    );
    litert::unload()?;
    Ok(())
}
