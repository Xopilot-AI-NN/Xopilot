// Описание: Открываем SQLCipher параллельно созданию WebView, а не после первого JS-кадра.
// Это не кеш незашифрованной истории на диске: подготовленный Store живёт только в процессе.
// Android Context уже установлен Tao/ndk-glue перед вызовом main, поэтому JNI доступен worker.
use super::{
    agent, chat_store, db::Store, task_history, ui_session,
};
use anyhow::{Result, anyhow};
use std::{
    collections::HashMap,
    sync::{Mutex, OnceLock},
    thread::JoinHandle,
};

pub struct Prepared {
    pub store: Store,
    pub snapshot: chat_store::Snapshot,
    pub model: Result<(String, bool)>,
    pub agent: agent::Settings,
    pub actions: HashMap<i64, Vec<task_history::Action>>,
    pub session: ui_session::Session,
}

static PREPARATION: OnceLock<
    Mutex<Option<JoinHandle<Result<Prepared>>>>,
> = OnceLock::new();

/// Запускается до dioxus::launch и сразу возвращает управление созданию нативного окна.
pub fn preload() {
    PREPARATION.get_or_init(|| {
        let worker = std::thread::Builder::new()
            .name("xopilot-startup".into())
            .spawn(load);
        if let Err(error) = &worker {
            tracing::warn!("Не удалось запустить предварительную подготовку: {error}");
        }
        Mutex::new(worker.ok())
    });
}

/// Выполняет те же проверки ключа и схемы, что обычный запуск. KDF SQLCipher не ослабляется.
fn load() -> Result<Prepared> {
    let began = std::time::Instant::now();
    let store = Store::open()?;
    super::profile::ensure_local(&store)?;
    let snapshot =
        store.with(|db| chat_store::load(db, None))?;
    let model = super::generation::label(&store);
    let agent = agent::settings(&store, snapshot.active)?;
    let actions =
        task_history::load(&store, &snapshot.messages)?;
    let session = ui_session::load(&store)?;
    tracing::info!(
        prepare_ms = began.elapsed().as_millis(),
        "Хранилище подготовлено"
    );
    Ok(Prepared {
        store,
        snapshot,
        model,
        agent,
        actions,
        session,
    })
}

/// Передаёт подготовленный результат первому UI; повторное открытие после ошибки допускает retry.
pub async fn take() -> Result<Prepared> {
    super::runtime::blocking(|| {
        let worker = PREPARATION
            .get()
            .and_then(|slot| slot.lock().ok()?.take());
        if let Some(worker) = worker {
            worker.join().map_err(|_| {
                anyhow!("Подготовка истории была прервана")
            })?
        } else {
            load()
        }
    })
    .await
}
