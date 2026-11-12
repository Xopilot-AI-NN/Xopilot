// Создано ChatGPT: демонстрация parent_id и параллельного потока для Flow Map v2.
// Демо работает с собственным временным файлом и не трогает пользовательские данные.
use std::io;
use xopilot::flow_trace as trace;

fn main() -> io::Result<()> {
    let session = trace::span("Демонстрация Xopilot");
    trace::step("Запуск обработки");
    let content = {
        let _scope = trace::span("Работа с файлом");
        let temporary = tempfile::NamedTempFile::new()?;
        trace::write(temporary.path(), "Привет, мир!")?;
        trace::read_to_string(temporary.path())?
    };
    let testingss = content.len();
    trace::variable("testingss", &testingss);
    trace::decision("testingss > 0", testingss > 0);
    if testingss > 0 {
        let parent = session.id().unwrap_or("").to_string();
        let worker = std::thread::spawn(move || {
            let _scope = trace::span_with_parent(
                "Фоновая задача",
                &parent,
            );
            trace::step(
                "Обработка данных в отдельном потоке",
            );
        });
        worker.join().map_err(|_| {
            io::Error::other(
                "Фоновый поток завершился с panic",
            )
        })?;
    }
    if std::env::var("FLOWMAP_STRESS").as_deref() == Ok("1")
    {
        let mut workers = Vec::new();
        for index in 0..4 {
            let parent =
                session.id().unwrap_or("").to_string();
            workers.push(std::thread::spawn(move || {
                let _scope = trace::span_with_parent(
                    &format!("Поток {index}"),
                    &parent,
                );
                for _ in 0..100 {
                    trace::step("Параллельная запись");
                }
            }));
        }
        for worker in workers {
            worker.join().expect("Поток демо");
        }
    }
    let parent = session.id().unwrap_or("").to_string();
    xopilot::services::runtime::runtime().block_on(async {
        let mut workers = Vec::new();
        for index in 0..2 {
            let parent = parent.clone();
            workers.push(tokio::spawn(async move {
                trace::scope_with_parent(
                    &format!("Async {index}"),
                    &parent,
                    async {
                        trace::step("Перед await");
                        tokio::task::yield_now().await;
                        trace::step("После await");
                    },
                )
                .await;
            }));
        }
        for worker in workers {
            worker.await.expect("Async демо");
        }
        let (sent, received) =
            tokio::sync::oneshot::channel();
        let cancelled = tokio::spawn(async move {
            trace::scope_with_parent(
                "Отменённая задача",
                &parent,
                async {
                    let _ = sent.send(());
                    std::future::pending::<()>().await;
                },
            )
            .await;
        });
        received.await.expect("Задача запущена");
        cancelled.abort();
        let _ = cancelled.await;
    });
    if std::env::var("FLOWMAP_TEST_ERROR").as_deref()
        == Ok("1")
    {
        let directory = tempfile::tempdir()?;
        assert!(
            trace::read_to_string(
                &directory.path().join("missing")
            )
            .is_err()
        );
    }
    trace::step("Готово");
    println!("Прочитано {testingss} байт");
    Ok(())
}
