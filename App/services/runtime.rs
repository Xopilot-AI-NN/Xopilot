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
pub async fn background<T: Send + 'static>(future: impl Future<Output = T> + Send + 'static) -> T {
    runtime()
        .spawn(future)
        .await
        .expect("Фоновая задача прервана")
}

/// Переносит файловую или вычислительную работу с потока интерфейса в worker.
pub async fn blocking<T: Send + 'static>(
    call: impl FnOnce() -> anyhow::Result<T> + Send + 'static,
) -> anyhow::Result<T> {
    background(async move { tokio::task::spawn_blocking(call).await? }).await
}
