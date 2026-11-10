// Файл: App/app/state.rs
// Описание: Состояние окна и обработчики; сервисы не зависят от Dioxus.
use crate::services::{
    self,
    chat_store::{Chat, Snapshot},
    db::Store,
    drafts::Draft,
};
use advanced_xopilot::db::StoredMessage;
use anyhow::{Context, Result};
use dioxus::prelude::*;
use tokio_util::sync::CancellationToken;

#[derive(Clone, Copy, PartialEq, Default)]
pub enum Screen {
    #[default]
    Chat,
    Settings,
    Workspaces,
    Canvas,
    Templates,
    Chats,
    Materials,
    Private,
    Model,
    Api,
    Account,
    Memory,
}

#[derive(Clone, Default)]
pub struct AppState {
    pub store: Option<Store>,
    pub chats: Vec<Chat>,
    pub active: Option<i64>,
    pub messages: Vec<StoredMessage>,
    pub bookmarks: std::collections::HashSet<i64>,
    pub draft: Draft,
    pub screen: Screen,
    pub sidebar: bool,
    pub theme: String,
    pub model: String,
    pub busy: bool,
    pub uploading: bool,
    pub streaming: String,
    pub cancelled: Option<CancellationToken>,
    pub error: Option<String>,
    pub ready: bool,
    pub unsaved: bool,
    pub pending_screen: Option<Screen>,
    pub pending_section: Option<Option<usize>>,
    pub workspace_name: String,
    pub notice: Option<String>,
    pub settings_section: Option<usize>,
    pub dialog_history: Vec<Screen>,
}

impl AppState {
    pub fn apply(&mut self, snapshot: Snapshot) {
        self.chats = snapshot.chats;
        self.active = Some(snapshot.active);
        self.messages = snapshot.messages;
        self.bookmarks = snapshot.bookmarks;
        self.draft = snapshot.draft;
        self.theme = snapshot.theme;
        self.workspace_name = snapshot.workspace_name;
    }
}

pub fn report(mut state: Signal<AppState>, result: Result<()>) {
    if let Err(error) = result {
        state.write().error = Some(format!("{error:#}"));
    }
}

pub fn store(state: Signal<AppState>) -> Result<Store> {
    state
        .read()
        .store
        .clone()
        .context("Хранилище ещё не открыто")
}

pub fn navigate(mut state: Signal<AppState>, screen: Screen) {
    let mut value = state.write();
    if value.uploading {
        value.error = Some("Дождитесь чтения вложений".into());
        return;
    }
    if value.unsaved && value.screen != screen {
        value.pending_screen = Some(screen);
    } else {
        if screen == Screen::Settings && value.screen == Screen::Chat {
            value.settings_section = None;
        }
        if screen == Screen::Chat {
            value.dialog_history.clear();
        } else if value.screen != Screen::Chat && value.screen != screen {
            let previous = value.screen;
            value.dialog_history.push(previous);
        }
        value.screen = screen;
        value.sidebar = false;
    }
}

pub fn dismiss(mut state: Signal<AppState>) {
    let mut value = state.write();
    let target = value.dialog_history.last().copied().unwrap_or(Screen::Chat);
    if value.unsaved {
        value.pending_screen = Some(target);
    } else {
        value.screen = value.dialog_history.pop().unwrap_or(Screen::Chat);
    }
}

pub fn discard_pending(mut state: Signal<AppState>) {
    let mut value = state.write();
    if let Some(section) = value.pending_section.take() {
        value.unsaved = false;
        value.settings_section = section;
        return;
    }
    if let Some(target) = value.pending_screen.take() {
        value.unsaved = false;
        if value.dialog_history.last() == Some(&target) {
            value.dialog_history.pop();
        }
        if target == Screen::Chat {
            value.dialog_history.clear();
        }
        value.screen = target;
    }
}

/// Возврат внутри настроек проходит ту же проверку, что и закрытие окна.
pub fn select_settings_section(mut state: Signal<AppState>, section: Option<usize>) {
    let mut value = state.write();
    if value.unsaved && value.settings_section != section {
        value.pending_section = Some(section);
    } else {
        value.settings_section = section;
    }
}

pub async fn initialize(mut state: Signal<AppState>) {
    let result = services::runtime::background(async move {
        tokio::task::spawn_blocking(|| -> Result<_> {
            let store = Store::open()?;
            let snapshot = store.with(|db| services::chat_store::load(db, None))?;
            let model = if services::api_chat::is_api_selected(&store)? {
                services::api_chat::configuration(&store).map(|config| config.model)
            } else {
                Ok(String::new())
            };
            Ok((store, snapshot, model))
        })
        .await?
    })
    .await;
    match result {
        Ok((store, snapshot, model)) => {
            let mut value = state.write();
            value.store = Some(store);
            value.apply(snapshot);
            value.error = None;
            match model {
                Ok(model) => value.model = model,
                Err(error) => value.error = Some(format!("Проверьте настройки API: {error:#}")),
            }
            value.ready = true;
        }
        Err(error) => {
            let mut value = state.write();
            value.error = Some(format!("Не удалось открыть защищённую историю: {error:#}"));
            value.ready = true;
        }
    }
}

pub async fn refresh(mut state: Signal<AppState>, requested: Option<i64>) -> Result<()> {
    let store = store(state)?;
    let snapshot = services::runtime::background(async move {
        services::chat_store::snapshot(&store, requested).await
    })
    .await?;
    let mut value = state.write();
    // Обновление заголовка/истории не должно затирать ещё набираемый текст.
    let draft = (value.active == Some(snapshot.active)).then(|| value.draft.clone());
    value.apply(snapshot);
    if let Some(draft) = draft {
        value.draft = draft;
    }
    Ok(())
}

pub async fn persist_draft(state: Signal<AppState>) -> Result<()> {
    let store = store(state)?;
    let (active, draft) = {
        let value = state.read();
        (value.active, value.draft.clone())
    };
    if let Some(id) = active {
        services::runtime::background(async move {
            store
                .run(move |db| services::drafts::write_draft(db, id, &draft))
                .await
        })
        .await?;
    }
    Ok(())
}

pub async fn switch_chat(mut state: Signal<AppState>, id: i64) -> Result<()> {
    anyhow::ensure!(!state.read().uploading, "Дождитесь чтения вложений");
    anyhow::ensure!(
        !state.read().unsaved,
        "Сохраните или закройте редактор перед сменой чата"
    );
    if state.read().busy {
        anyhow::bail!("Остановите текущий ответ перед сменой чата");
    }
    persist_draft(state).await?;
    refresh(state, Some(id)).await?;
    let mut value = state.write();
    value.screen = Screen::Chat;
    value.dialog_history.clear();
    value.sidebar = false;
    Ok(())
}

pub async fn new_chat(mut state: Signal<AppState>) -> Result<()> {
    anyhow::ensure!(!state.read().uploading, "Дождитесь чтения вложений");
    anyhow::ensure!(
        !state.read().unsaved,
        "Сохраните или закройте редактор перед созданием чата"
    );
    if state.read().busy {
        anyhow::bail!("Остановите текущий ответ перед созданием чата");
    }
    persist_draft(state).await?;
    let store = store(state)?;
    let id = services::runtime::background(async move {
        store.run(|db| Ok(db.create_chat("Новый чат")?)).await
    })
    .await?;
    refresh(state, Some(id)).await?;
    state.write().screen = Screen::Chat;
    state.write().dialog_history.clear();
    state.write().sidebar = false;
    Ok(())
}

pub async fn delete_chat(state: Signal<AppState>, id: i64) -> Result<()> {
    anyhow::ensure!(!state.read().uploading, "Дождитесь чтения вложений");
    if state.read().busy {
        anyhow::bail!("Остановите текущий ответ перед удалением чата");
    }
    let store = store(state)?;
    services::runtime::background(async move {
        store
            .run(move |db| {
                db.delete_chat(id)?;
                Ok(())
            })
            .await
    })
    .await?;
    refresh(state, None).await
}

pub async fn send(mut state: Signal<AppState>) -> Result<()> {
    anyhow::ensure!(!state.read().uploading, "Дождитесь чтения вложений");
    if state.read().busy {
        return Ok(());
    }
    let (id, draft) = {
        let value = state.read();
        (value.active.context("Чат не выбран")?, value.draft.clone())
    };
    if draft.text.trim().is_empty() && draft.files.is_empty() {
        return Ok(());
    }
    let store = store(state)?;
    // Блокируем повторный Enter до первого await.
    let token = CancellationToken::new();
    {
        let mut value = state.write();
        value.busy = true;
        value.streaming.clear();
        value.cancelled = Some(token.clone());
        value.error = None;
    }
    let started = std::time::Instant::now();
    let worker_store = store.clone();
    let prepared = services::runtime::background(async move {
        tokio::task::spawn_blocking(move || -> Result<_> {
            let config = services::api_chat::selected_configuration(&worker_store)?;
            let workspace = services::workspaces::chat_workspace(&worker_store, id)?;
            let instructions = format!(
                "{}\n{}",
                services::profile::instructions(&worker_store)?,
                workspace.instructions
            );
            let history = worker_store.with(|db| {
                db.add_message_full(id, "user", &draft.text, None, None, &draft.files, None)?;
                let history = db.get_messages(id)?;
                if history.len() == 1 {
                    let title = if draft.text.trim().is_empty() {
                        draft
                            .files
                            .first()
                            .map(|f| f.0.as_str())
                            .unwrap_or("Новый чат")
                    } else {
                        draft.text.trim()
                    };
                    db.rename_chat(id, &title.chars().take(50).collect::<String>())?;
                }
                services::drafts::write_draft(db, id, &Draft::default())?;
                Ok(history)
            })?;
            // PDF и изображения читаются без удержания блокировки хранилища.
            let messages = services::api_chat::build_messages(&history, &instructions);
            Ok((config, messages))
        })
        .await?
    })
    .await;
    let result = async {
        let (config, messages) = prepared?;
        // После сохранения запроса очищаем редактор. При ошибке настройки черновик остаётся.
        state.write().draft = Draft::default();
        refresh(state, Some(id)).await?;
        let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel();
        let request_token = token.clone();
        let task = services::runtime::runtime().spawn(async move {
            services::api_chat::generate_reply(config, messages, request_token, tx).await
        });
        while let Some(delta) = rx.recv().await {
            state.write().streaming.push_str(&delta);
        }
        let answer = task.await??;
        let elapsed = started.elapsed().as_secs_f64();
        services::runtime::background(async move {
            store
                .run(move |db| {
                    db.add_message_full(id, "ai", &answer, None, None, &[], Some(elapsed))?;
                    Ok(())
                })
                .await
        })
        .await?;
        refresh(state, Some(id)).await?;
        Ok(())
    }
    .await;
    {
        let mut value = state.write();
        value.busy = false;
        value.cancelled = None;
        value.streaming.clear();
    }
    if token.is_cancelled() { Ok(()) } else { result }
}

pub fn cancel(state: Signal<AppState>) {
    if let Some(token) = &state.read().cancelled {
        token.cancel();
    }
}

pub async fn export_chat(mut state: Signal<AppState>) -> Result<()> {
    let store = store(state)?;
    let id = state.read().active.context("Чат не выбран")?;
    let path = services::runtime::blocking(move || {
        store.with(|db| {
            let title = db
                .list_chats()?
                .into_iter()
                .find(|c| c.0 == id)
                .map(|c| c.1)
                .unwrap_or_default();
            services::exports::save_markdown(&title, &db.get_messages(id)?)
        })
    })
    .await?;
    state.write().notice = Some(format!("Экспорт сохранён: {}", path.display()));
    Ok(())
}
