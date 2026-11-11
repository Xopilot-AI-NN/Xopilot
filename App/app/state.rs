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
    pub session_revision: u64,
    pub chats: Vec<Chat>,
    pub active: Option<i64>,
    pub messages: Vec<StoredMessage>,
    pub bookmarks: std::collections::HashSet<i64>,
    pub draft: Draft,
    pub screen: Screen,
    pub sidebar: bool,
    pub theme: String,
    pub model: String,
    pub model_local: bool,
    pub agent: services::agent::Settings,
    pub agent_control: Option<services::agent::Control>,
    pub agent_progress: String,
    pub action_history: std::collections::HashMap<i64, Vec<services::task_history::Action>>,
    pub task_completion: Option<(String, bool)>,
    pub dismissed_downloads: std::collections::HashSet<String>,
    pub approval: Option<services::agent::Approval>,
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
    /// Применяет снимок текущего чата к сигналам окна.
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

/// Передаёт ошибку действия в общий блок уведомлений над вводом.
pub fn report(mut state: Signal<AppState>, result: Result<()>) {
    if let Err(error) = result {
        state.write().error = Some(format!("{error:#}"));
    }
}

/// Создаёт или получает хранилище данных текущего контекста.
pub fn store(state: Signal<AppState>) -> Result<Store> {
    state
        .read()
        .store
        .clone()
        .context("Хранилище ещё не открыто")
}

/// Открывает раздел с учётом несохранённой формы и истории возврата.
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

/// Возвращается к предыдущему окну, не теряя изменённую форму.
pub fn dismiss(mut state: Signal<AppState>) {
    let mut value = state.write();
    let target = value.dialog_history.last().copied().unwrap_or(Screen::Chat);
    if value.unsaved {
        value.pending_screen = Some(target);
    } else {
        value.screen = value.dialog_history.pop().unwrap_or(Screen::Chat);
    }
}

/// Подтверждает отложенный переход и снимает признак несохранённых изменений.
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

/// Открывает защищённую базу и восстанавливает профиль, чат и настройки.
pub async fn initialize(mut state: Signal<AppState>) {
    let result = services::runtime::background(async move {
        tokio::task::spawn_blocking(|| -> Result<_> {
            let store = Store::open()?;
            services::profile::ensure_local(&store)?;
            let snapshot = store.with(|db| services::chat_store::load(db, None))?;
            let model = services::generation::label(&store);
            let agent = services::agent::settings(&store, snapshot.active)?;
            let actions = services::task_history::load(&store, &snapshot.messages)?;
            Ok((store, snapshot, model, agent, actions))
        })
        .await?
    })
    .await;
    match result {
        Ok((store, snapshot, model, agent, actions)) => {
            let mut value = state.write();
            value.store = Some(store);
            value.agent = agent;
            value.action_history = actions;
            value.apply(snapshot);
            value.error = None;
            match model {
                Ok((model, local)) => {
                    value.model = model;
                    value.model_local = local;
                }
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

/// Обновляет сообщения и действия текущего чата, сохраняя набираемый черновик.
pub async fn refresh(mut state: Signal<AppState>, requested: Option<i64>) -> Result<()> {
    let store = store(state)?;
    let snapshot = services::runtime::background(async move {
        let snapshot = services::chat_store::snapshot(&store, requested).await?;
        let agent = services::agent::settings(&store, snapshot.active)?;
        let actions = services::task_history::load(&store, &snapshot.messages)?;
        Ok::<_, anyhow::Error>((snapshot, agent, actions))
    })
    .await?;
    let (snapshot, agent, actions) = snapshot;
    let mut value = state.write();
    // Обновление заголовка/истории не должно затирать ещё набираемый текст.
    let draft = (value.active == Some(snapshot.active)).then(|| value.draft.clone());
    value.apply(snapshot);
    value.agent = agent;
    value.action_history = actions;
    if let Some(draft) = draft {
        value.draft = draft;
    }
    Ok(())
}

/// Сохраняет текст и вложения перед переключением чата.
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

/// Переключает чат после проверки занятости и сбрасывает контекст модели.
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
    services::runtime::blocking(services::litert::reset_context).await?;
    refresh(state, Some(id)).await?;
    let mut value = state.write();
    value.screen = Screen::Chat;
    value.dialog_history.clear();
    value.sidebar = false;
    Ok(())
}

/// Создаёт пустой чат, предварительно сохранив предыдущий черновик.
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
    services::runtime::blocking(services::litert::reset_context).await?;
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

/// Удаляет выбранный чат и обновляет доступную историю.
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
    services::runtime::blocking(services::litert::reset_context).await?;
    refresh(state, None).await
}

/// Сохраняет запрос, принимает поток ответа и результаты инструментов, затем обновляет историю.
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
        value.task_completion = None;
    }
    let started = std::time::Instant::now();
    let worker_store = store.clone();
    let agent_settings = state.read().agent.clone();
    let control = services::agent::Control::default();
    state.write().agent_control = Some(control.clone());
    let prepared = services::runtime::background(async move {
        tokio::task::spawn_blocking(move || -> Result<_> {
            let config = services::generation::selected(&worker_store)?;
            let workspace = services::workspaces::chat_workspace(&worker_store, id)?;
            let instructions = format!(
                "{}\n{}",
                services::profile::instructions(&worker_store)?,
                workspace.instructions
            );
            let history = worker_store.with(|db| {
                let request_id =
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
                Ok((history, request_id))
            })?;
            // PDF и изображения читаются без удержания блокировки хранилища.
            let messages = services::api_chat::build_messages(&history.0, &instructions);
            Ok((config, messages, workspace, history.1))
        })
        .await?
    })
    .await;
    let result = async {
        let (config, messages, workspace, request_id) = prepared?;
        // После сохранения запроса очищаем редактор; при ошибке настроек черновик остаётся.
        state.write().draft = Draft::default();
        refresh(state, Some(id)).await?;
        let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel();
        let request_token = token.clone();
        let (events, mut event_rx) = tokio::sync::mpsc::unbounded_channel();
        let worker_settings = agent_settings.clone();
        let context = services::agent::ContextData {
            store: store.clone(),
            chat: id,
            workspace,
            settings: worker_settings.clone(),
            control,
            events,
        };
        let task = services::runtime::runtime().spawn(async move {
            if worker_settings.enabled {
                services::agent::run(config, messages, request_token, tx, context).await
            } else {
                drop(context);
                services::generation::reply(config, messages, request_token, tx).await
            }
        });
        let (mut text_open, mut events_open) = (true, true);
        while text_open || events_open {
            tokio::select! {
                delta = rx.recv(), if text_open => {
                    match delta {
                        Some(delta) => state.write().streaming.push_str(&delta),
                        None => text_open = false,
                    }
                }
                event = event_rx.recv(), if events_open => {
                    match event {
                        Some(services::agent::Event::Progress(progress)) => {
                            state.write().agent_progress = progress;
                        }
                        Some(services::agent::Event::Approval(approval)) => {
                            let mut value = state.write();
                            if let Some(action) = value.action_history.entry(request_id).or_default().last_mut() {
                                action.state = "approval".into();
                            }
                            value.approval = Some(approval);
                        }
                        Some(services::agent::Event::ToolResult { .. }) => {}
                        Some(services::agent::Event::ToolStarted { id, tool, arguments }) => {
                            state.write().action_history.entry(request_id).or_default().push(
                                services::task_history::Action {
                                    id,
                                    tool,
                                    arguments,
                                    state: "running".into(),
                                    ..Default::default()
                                },
                            );
                        }
                        Some(services::agent::Event::ToolFinished { id, output, seconds }) => {
                            if let Some(action) = state.write().action_history.entry(request_id)
                                .or_default().iter_mut().find(|action| action.id == id)
                            {
                                action.state = if output["ok"] == true { "completed" } else { "failed" }.into();
                                action.output = output;
                                action.seconds = seconds;
                            }
                        }
                        None => events_open = false,
                    }
                }
            }
        }
        let actions = state.peek().action_history.get(&request_id).cloned().unwrap_or_default();
        if !actions.is_empty() {
            let store = store.clone();
            services::runtime::blocking(move || {
                services::task_history::save(&store, request_id, &actions)
            }).await?;
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
        value.agent_control = None;
        value.agent_progress.clear();
        value.approval = None;
        value.streaming.clear();
        if agent_settings.enabled {
            let actions = value
                .messages
                .iter()
                .rev()
                .find(|m| m.role == "user")
                .and_then(|m| value.action_history.get(&m.id));
            let tools_ok =
                actions.is_none_or(|actions| actions.iter().all(|a| a.state == "completed"));
            let count = actions.map_or(0, Vec::len);
            value.task_completion = Some(if token.is_cancelled() {
                ("Задача остановлена".into(), false)
            } else if result.is_ok() && tools_ok {
                (
                    if count == 0 {
                        "Ответ готов".into()
                    } else {
                        format!("Работа агента завершена · {count} действий")
                    },
                    true,
                )
            } else {
                ("Есть невыполненные действия".into(), false)
            });
        }
    }
    if token.is_cancelled() { Ok(()) } else { result }
}

/// Отмечает ожидание решения в карточке и однократно отвечает запросу подтверждения.
pub fn answer_action(mut state: Signal<AppState>, accepted: bool) {
    let mut value = state.write();
    for action in value.action_history.values_mut().flatten() {
        if action.state == "approval" {
            action.state = if accepted { "running" } else { "failed" }.into();
        }
    }
    if let Some(approval) = value.approval.take() {
        approval.answer(accepted);
    }
}

/// Отменяет активную генерацию и выполняемые инструменты через общий токен.
pub fn cancel(state: Signal<AppState>) {
    if let Some(token) = &state.read().cancelled {
        token.cancel();
    }
}

/// Записывает переписку выбранного чата в Markdown.
pub async fn export_chat(mut state: Signal<AppState>) -> Result<()> {
    let store = store(state)?;
    let root = services::paths::app_data_dir()?;
    let id = state.read().active.context("Чат не выбран")?;
    let path = services::runtime::blocking(move || {
        store.with(|db| {
            let title = db
                .list_chats()?
                .into_iter()
                .find(|c| c.0 == id)
                .map(|c| c.1)
                .unwrap_or_default();
            services::exports::save_markdown_at(&root, &title, &db.get_messages(id)?)
        })
    })
    .await?;
    state.write().notice = Some(format!("Экспорт сохранён: {}", path.display()));
    Ok(())
}
