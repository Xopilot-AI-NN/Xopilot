// Создано ChatGPT: расширенный трассировщик Xopilot Flow Map v3.
// Сохраняет совместимость с предыдущими begin/step/call/variable/read_to_string/write.
// Новое: явные идентификаторы событий, parent_id и вложенные span-блоки.

use serde_json::json;
use std::cell::RefCell;
use std::fmt::Debug;
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Seek, SeekFrom, Write};
use std::marker::PhantomData;
use std::panic::Location;
use std::path::{Path, PathBuf};
use std::rc::Rc;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};

struct TraceState {
    started: Instant,
    session: String,
    max_events: u64,
    bytes: AtomicU64,
    failed: AtomicBool,
    sequence: AtomicU64,
    output: Mutex<File>,
    _lease: File,
}

static STATE: OnceLock<Option<TraceState>> =
    OnceLock::new();
thread_local! {
    // Для async-задач, перемещающихся между потоками, передавай ID через span_with_parent.
    static SPAN_STACK: RefCell<Vec<String>> = const { RefCell::new(Vec::new()) };
}

/// Открывает один локальный журнал процесса при первом включённом событии.
fn state() -> Option<&'static TraceState> {
    STATE
        .get_or_init(|| {
            if std::env::var("XOPILOT_FLOW_TRACE").as_deref() != Ok("1") {
                return None;
            }
            let path = std::env::var_os("XOPILOT_FLOW_PATH")
                .map(PathBuf::from)
                .unwrap_or_else(|| {
                    PathBuf::from(format!(
                        "target/flow-traces/xopilot-{}.jsonl",
                        std::process::id()
                    ))
                });
            let opened = (|| -> io::Result<(File, File)> {
                if let Some(parent) = path.parent().filter(|p| !p.as_os_str().is_empty()) {
                    fs::create_dir_all(parent)?;
                }
                // Lock-файл отделён от данных, чтобы Windows позволяла читать
                // сам журнал в браузере при работающем процессе-писателе.
                let mut lock_path = path.as_os_str().to_os_string();
                lock_path.push(".lock");
                let mut lock_options = OpenOptions::new();
                lock_options.create(true).read(true).write(true).truncate(false);
                #[cfg(unix)] {
                    use std::os::unix::fs::OpenOptionsExt;
                    lock_options.mode(0o600);
                }
                let lease = lock_options.open(lock_path)?;
                fs2::FileExt::try_lock_exclusive(&lease).map_err(|error| {
                    io::Error::new(error.kind(), format!("Журнал уже занят: {error}"))
                })?;
                let mut options = OpenOptions::new();
                options.create(true).append(true).read(true);
                #[cfg(unix)] {
                    use std::os::unix::fs::OpenOptionsExt;
                    options.mode(0o600);
                }
                let mut file = options.open(&path)?;
                if file.metadata()?.len() > 0 {
                    file.seek(SeekFrom::End(-1))?;
                    let mut last = [0];
                    file.read_exact(&mut last)?;
                    if last[0] != b'\n' {
                        return Err(io::Error::new(io::ErrorKind::InvalidData,
                            "Журнал содержит незавершённую строку. Выберите новый XOPILOT_FLOW_PATH"));
                    }
                }
                Ok((file, lease))
            })();
            match opened {
                Ok((file, lease)) => {
                    eprintln!("[Flow Map v3] Трассировка: {}", path.display());
                    let bytes = file.metadata().map(|metadata| metadata.len()).unwrap_or(0);
                    Some(TraceState {
                        started: Instant::now(),
                        session: uuid::Uuid::new_v4().to_string(),
                        bytes: AtomicU64::new(bytes),
                        failed: AtomicBool::new(false),
                        max_events: std::env::var("XOPILOT_FLOW_MAX_EVENTS")
                            .ok()
                            .and_then(|v| v.parse().ok())
                            .unwrap_or(100_000),
                        sequence: AtomicU64::new(0),
                        output: Mutex::new(file),
                        _lease: lease,
                    })
                }
                Err(err) => {
                    eprintln!("[Flow Map v3] Ошибка файла трассировки: {err}");
                    None
                }
            }
        })
        .as_ref()
}

/// Возвращает верхушку синхронного стека текущего потока.
fn current_parent() -> Option<String> {
    SPAN_STACK
        .try_with(|stack| {
            stack
                .try_borrow()
                .ok()
                .and_then(|s| s.last().cloned())
        })
        .ok()
        .flatten()
}

#[track_caller]
fn record(
    kind: &str,
    name: &str,
    detail: &str,
    parent_override: Option<&str>,
) -> Option<String> {
    record_timed(kind, name, detail, parent_override, None)
}

/// Номер и время назначаются под тем же mutex, что и запись строки.
/// Уникальная сессия отделяет повторные запуски, дописанные в один журнал.
#[track_caller]
fn record_timed(
    kind: &str,
    name: &str,
    detail: &str,
    parent_override: Option<&str>,
    duration_ms: Option<u128>,
) -> Option<String> {
    let trace = state()?;
    if trace.failed.load(Ordering::Relaxed)
        || trace.sequence.load(Ordering::Relaxed)
            >= trace.max_events
    {
        return None;
    }
    let mut file = trace.output.lock().ok()?;
    if trace.failed.load(Ordering::Relaxed) {
        return None;
    }
    let seq =
        trace.sequence.fetch_add(1, Ordering::Relaxed) + 1;
    if seq > trace.max_events
        || trace.bytes.load(Ordering::Relaxed)
            >= 64 * 1024 * 1024
    {
        return None;
    }
    let id = format!("{}:{seq}", trace.session);
    let parent = parent_override
        .filter(|p| !p.trim().is_empty())
        .map(str::to_owned)
        .or_else(current_parent);
    let source = Location::caller();
    let event = json!({
        "version": 3, "session": trace.session, "id": id,
        "parent_id": parent, "seq": seq, "ms": trace.started.elapsed().as_millis(),
        "kind": kind, "name": truncate_utf8(name, 1000), "detail": truncate_utf8(detail, 4000),
        "thread": format!("{:?}", std::thread::current().id()),
        "file": source.file(), "line": source.line(), "column": source.column(),
        "duration_ms": duration_ms,
    });
    let line = serde_json::to_vec(&event).ok()?;
    let length = line.len() as u64 + 1;
    if trace.bytes.load(Ordering::Relaxed) + length
        > 64 * 1024 * 1024
    {
        return None;
    }
    if file
        .write_all(&line)
        .and_then(|_| file.write_all(b"\n"))
        .is_err()
    {
        trace.failed.store(true, Ordering::Relaxed);
        return None;
    }
    trace.bytes.fetch_add(length, Ordering::Relaxed);
    Some(id)
}

/// Синхронная область выполнения, которая создаёт связь parent_id для вложенных событий.
/// Не переносится между потоками; в async используй span_with_parent с явным ID.
pub struct FlowSpan {
    id: Option<String>,
    name: String,
    started: Instant,
    _not_send: PhantomData<Rc<()>>,
}

impl FlowSpan {
    /// ID области, который можно передать в другой поток или задачу.
    pub fn id(&self) -> Option<&str> {
        self.id.as_deref()
    }
}

impl Drop for FlowSpan {
    fn drop(&mut self) {
        let Some(id) = self.id.as_ref() else { return };
        // Завершение записывается до снятия области, чтобы связь осталась однозначной.
        let _ = record_timed(
            "end",
            &format!("Завершено: {}", self.name),
            if std::thread::panicking() {
                "panic"
            } else {
                ""
            },
            Some(id),
            Some(self.started.elapsed().as_millis()),
        );
        let _ = SPAN_STACK.try_with(|stack| {
            if let Ok(mut stack) = stack.try_borrow_mut() {
                if stack
                    .last()
                    .is_some_and(|current| current == id)
                {
                    stack.pop();
                } else if let Some(position) = stack
                    .iter()
                    .rposition(|current| current == id)
                {
                    stack.remove(position);
                }
            }
        });
    }
}

/// Создаёт синхронную вложенную область с завершением при Drop.
#[track_caller]
pub fn span(name: &str) -> FlowSpan {
    span_with_parent(name, "")
}

/// Явно указывает родителя при переносе работы в другой поток / async-задачу.
#[track_caller]
pub fn span_with_parent(
    name: &str,
    parent_id: &str,
) -> FlowSpan {
    let id = record("call", name, "", Some(parent_id));
    if let Some(id) = &id {
        let _ = SPAN_STACK.try_with(|stack| {
            if let Ok(mut stack) = stack.try_borrow_mut() {
                stack.push(id.clone());
            }
        });
    }
    FlowSpan {
        id,
        name: name.to_owned(),
        started: Instant::now(),
        _not_send: PhantomData,
    }
}

/// Отмечает начало этапа без создания вложенного guard.
#[track_caller]
pub fn begin(name: &str) {
    let _ = record("start", name, "", None);
}
/// Записывает наблюдаемый шаг внутри активной операции.
#[track_caller]
pub fn step(name: &str) {
    let _ = record("step", name, "", None);
}
/// Отмечает вызов без автоматического завершения.
#[track_caller]
pub fn call(name: &str) {
    let _ = record("call", name, "", None);
}
/// Сохраняет фактически выбранное значение условия.
#[track_caller]
pub fn decision(name: &str, condition: bool) {
    let _ = record(
        "branch",
        name,
        if condition { "true" } else { "false" },
        None,
    );
}
#[track_caller]
pub fn error(name: &str, err: &impl std::fmt::Display) {
    // Текст ошибки может содержать путь или данные; не логируй ошибки с секретами.
    let _ = record("error", name, &err.to_string(), None);
}
/// Отмечает завершение вручную размеченного этапа.
#[track_caller]
pub fn end(name: &str) {
    let _ = record("end", name, "", None);
}

/// Запись значения требует явного XOPILOT_FLOW_VALUES=1.
/// Никогда не передавай сюда пароли, токены или содержимое личных чатов.
#[track_caller]
pub fn variable(name: &str, value: &impl Debug) {
    if state().is_none() {
        return;
    }
    let detail = if std::env::var("XOPILOT_FLOW_VALUES")
        .as_deref()
        == Ok("1")
    {
        truncate_utf8(&format!("{value:?}"), 200)
    } else {
        "[значение скрыто; XOPILOT_FLOW_VALUES=1]"
            .to_string()
    };
    let _ = record("variable", name, &detail, None);
}

/// Ограничивает текст по Unicode-символам, сохраняя корректный UTF-8.
fn truncate_utf8(value: &str, max_chars: usize) -> String {
    let mut chars = value.chars();
    let result: String =
        chars.by_ref().take(max_chars).collect();
    if chars.next().is_some() {
        format!("{result}…")
    } else {
        result
    }
}

#[track_caller]
pub fn read_to_string(path: &Path) -> io::Result<String> {
    let started = Instant::now();
    let _operation = operation(
        "file_read",
        "Чтение файла",
        &path.display().to_string(),
    );
    match fs::read_to_string(path) {
        Ok(data) => {
            let _ = record(
                "step",
                "Файл прочитан",
                &format!(
                    "{} байт, {} мс",
                    data.len(),
                    elapsed_ms(started.elapsed())
                ),
                None,
            );
            Ok(data)
        }
        Err(err) => {
            error("Ошибка чтения файла", &err);
            Err(err)
        }
    }
}

/// Как std::fs::write: перезаписывает содержимое пути. Не вызывай для одних лишь логов.
#[track_caller]
pub fn write(path: &Path, content: &str) -> io::Result<()> {
    let started = Instant::now();
    let _operation = operation(
        "file_write",
        "Запись файла",
        &path.display().to_string(),
    );
    match fs::write(path, content) {
        Ok(()) => {
            let _ = record(
                "step",
                "Файл записан",
                &format!(
                    "{} байт, {} мс",
                    content.len(),
                    elapsed_ms(started.elapsed())
                ),
                None,
            );
            Ok(())
        }
        Err(err) => {
            error("Ошибка записи файла", &err);
            Err(err)
        }
    }
}

/// Преобразует длительность операции в миллисекунды.
fn elapsed_ms(duration: Duration) -> u128 {
    duration.as_millis()
}

/// Область файловой операции связывает результат и ошибку с её началом.
#[track_caller]
fn operation(
    kind: &str,
    name: &str,
    detail: &str,
) -> FlowSpan {
    let id = record(kind, name, detail, None);
    if let Some(id) = &id {
        SPAN_STACK.with(|stack| {
            stack.borrow_mut().push(id.clone())
        });
    }
    FlowSpan {
        id,
        name: name.into(),
        started: Instant::now(),
        _not_send: PhantomData,
    }
}

/// Контекст устанавливается только на время poll и снимается до Pending.
/// Поэтому Future можно переносить между потоками исполнителя Tokio.
pub async fn scope<F: std::future::Future>(
    name: &str,
    future: F,
) -> F::Output {
    let parent = current_parent().unwrap_or_default();
    scope_with_parent(name, &parent, future).await
}

/// Передаёт причинность в независимую async-задачу по явному ID родителя.
pub async fn scope_with_parent<F: std::future::Future>(
    name: &str,
    parent: &str,
    future: F,
) -> F::Output {
    if state().is_none() {
        return future.await;
    }
    let mut lifetime = AsyncLifetime {
        id: record("call", name, "async", Some(parent)),
        name: name.into(),
        started: Instant::now(),
        completed: false,
    };
    let mut future = std::pin::pin!(future);
    let result = std::future::poll_fn(|context| {
        let _parent =
            PollParent::enter(lifetime.id.as_deref());
        future.as_mut().poll(context)
    })
    .await;
    lifetime.completed = true;
    result
}

struct PollParent(Option<String>);
impl PollParent {
    /// Стек хранит только активный poll, без ожидания async-операции.
    fn enter(id: Option<&str>) -> Self {
        let id = id.map(str::to_owned);
        if let Some(id) = &id {
            SPAN_STACK.with(|stack| {
                stack.borrow_mut().push(id.clone())
            });
        }
        Self(id)
    }
}
impl Drop for PollParent {
    /// Восстанавливает контекст соседней задачи, в том числе при panic.
    fn drop(&mut self) {
        if let Some(id) = &self.0 {
            SPAN_STACK.with(|stack| {
                let mut stack = stack.borrow_mut();
                if let Some(position) = stack
                    .iter()
                    .rposition(|current| current == id)
                {
                    stack.remove(position);
                }
            });
        }
    }
}
struct AsyncLifetime {
    id: Option<String>,
    name: String,
    started: Instant,
    completed: bool,
}
impl Drop for AsyncLifetime {
    /// Drop отмечает также отменённую Future, не удерживая thread-local контекст.
    fn drop(&mut self) {
        if let Some(id) = &self.id {
            record_timed(
                "end",
                &self.name,
                if std::thread::panicking() {
                    "panic"
                } else if self.completed {
                    "completed"
                } else {
                    "cancelled"
                },
                Some(id),
                Some(self.started.elapsed().as_millis()),
            );
        }
    }
}

/// Токен активной операции для передачи в отдельный поток или задачу.
pub fn current_id() -> Option<String> {
    current_parent()
}

#[cfg(test)]
mod tests {
    use super::truncate_utf8;
    #[test]
    fn utf8_truncation_preserves_char_boundaries() {
        assert_eq!(truncate_utf8("абвг", 3), "абв…");
        assert_eq!(truncate_utf8("hello", 5), "hello");
        assert_eq!(truncate_utf8("", 3), "");
    }
}
