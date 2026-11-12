// Описание: Общий Tokio runtime для фоновых сервисов и тестов интерфейса.
use std::sync::OnceLock;
use tokio::runtime::{Builder, Runtime};

/// Лениво создаёт один общий Tokio runtime для фоновой работы.
pub fn runtime() -> &'static Runtime {
    static RUNTIME: OnceLock<Runtime> = OnceLock::new();
    RUNTIME.get_or_init(|| {
        Builder::new_multi_thread()
            .enable_all()
            .build()
            .expect("Tokio runtime")
    })
}

/// Выполняет сетевую или асинхронную задачу вне исполнителя Dioxus.
pub async fn background<T: Send + 'static>(
    future: impl Future<Output = T> + Send + 'static,
) -> T {
    let parent =
        crate::flow_trace::current_id().unwrap_or_default();
    runtime()
        .spawn(async move {
            crate::flow_trace::scope_with_parent(
                "Фоновая задача",
                &parent,
                future,
            )
            .await
        })
        .await
        .expect("Фоновая задача прервана")
}

/// Переносит файловую или вычислительную работу с потока интерфейса в worker.
pub async fn blocking<T: Send + 'static>(
    call: impl FnOnce() -> anyhow::Result<T> + Send + 'static,
) -> anyhow::Result<T> {
    background(async move {
        let parent = crate::flow_trace::current_id()
            .unwrap_or_default();
        tokio::task::spawn_blocking(move || {
            let _operation =
                crate::flow_trace::span_with_parent(
                    "Блокирующая операция",
                    &parent,
                );
            call()
        })
        .await?
    })
    .await
}
