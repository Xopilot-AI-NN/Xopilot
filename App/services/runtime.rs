// Описание: Общий Tokio runtime для фоновых сервисов и тестов интерфейса.
use std::sync::OnceLock;
use tokio::runtime::{Builder, Runtime};

pub fn runtime() -> &'static Runtime {
    static RUNTIME: OnceLock<Runtime> = OnceLock::new();
    RUNTIME.get_or_init(|| {
        Builder::new_multi_thread()
            .enable_all()
            .build()
            .expect("Tokio runtime")
    })
}

pub async fn background<T: Send + 'static>(future: impl Future<Output = T> + Send + 'static) -> T {
    runtime()
        .spawn(future)
        .await
        .expect("Фоновая задача прервана")
}

pub async fn blocking<T: Send + 'static>(
    call: impl FnOnce() -> anyhow::Result<T> + Send + 'static,
) -> anyhow::Result<T> {
    background(async move { tokio::task::spawn_blocking(call).await? }).await
}
