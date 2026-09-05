// Файл: Services/src/lib.rs
// Проект: Xopilot AI+ NN+
// Разработчик: DenBroLiik
// Версия: 1.0.0
// Описание: Rust-библиотека (cdylib) с PyO3-биндингом для Flet/Python UI.
//              Шифрование — всегда включено, ключ берётся автоматически из OS keyring (security::get_or_create_db_key).
//              cloud_sync / mcp / updates — заглушки под фазу 2.

mod cloud_sync;
mod db;
mod mcp;
mod security;
mod updates;

use db::{Database, StoredMessage};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::sync::Mutex;

/// Обёртка rusqlite::Error в исключение Python, чтобы ошибки БД красиво ловились на стороне Flet (try/except), а не роняли процесс.
fn to_py_err(e: rusqlite::Error) -> PyErr {
    PyRuntimeError::new_err(e.to_string())
}

/// Python-представление одного сообщения из БД. Поля читаются из Python как `msg.id`, `msg.quote` и т.д.
#[pyclass]
struct PyMessage {
    #[pyo3(get)]
    id: i64,
    #[pyo3(get)]
    role: String,
    #[pyo3(get)]
    content: String,
    #[pyo3(get)]
    quote: Option<String>,
    #[pyo3(get)]
    reply_to: Option<String>,
    /// Список (имя, путь) для каждого вложения.
    #[pyo3(get)]
    attachments: Vec<(String, String)>,
    #[pyo3(get)]
    created_at: i64,
}

impl From<StoredMessage> for PyMessage {
    fn from(m: StoredMessage) -> Self {
        PyMessage {
            id: m.id,
            role: m.role,
            content: m.content,
            quote: m.quote,
            reply_to: m.reply_to,
            attachments: m.attachments,
            created_at: m.created_at,
        }
    }
}

/// Python-обёртка над db::Database. Mutex — потому что PyO3-объекты должны быть Sync,
/// а rusqlite::Connection — нет (в десктопном клиенте конкурентного доступа и так не будет, накладные расходы минимальны).
#[pyclass]
struct PyDatabase {
    inner: Mutex<Database>,
}

#[pymethods]
impl PyDatabase {
    /// PyDatabase(path) — ключ больше не передаётся из Python: берётся автоматически из OS keyring
    /// (или из фоллбэка на основе machine-id, если keyring недоступен).
    #[new]
    fn new(path: String) -> PyResult<Self> {
        let db_path = std::path::PathBuf::from(&path);
        let fallback_dir = db_path
            .parent()
            .map(|p| p.to_path_buf())
            .unwrap_or_else(|| std::path::PathBuf::from("."));

        let key = security::get_or_create_db_key(&fallback_dir);
        let db = Database::open(&path, &key).map_err(to_py_err)?;
        Ok(PyDatabase {
            inner: Mutex::new(db),
        })
    }

    fn set_setting(&self, key: String, value: String) -> PyResult<()> {
        self.inner
            .lock()
            .unwrap()
            .set_setting(&key, &value)
            .map_err(to_py_err)
    }

    fn get_setting(&self, key: String) -> PyResult<Option<String>> {
        self.inner.lock().unwrap().get_setting(&key).map_err(to_py_err)
    }

    fn all_settings(&self) -> PyResult<Vec<(String, String, i64)>> {
        self.inner.lock().unwrap().all_settings().map_err(to_py_err)
    }

    fn create_chat(&self, title: String) -> PyResult<i64> {
        self.inner.lock().unwrap().create_chat(&title).map_err(to_py_err)
    }

    /// quote/reply_to — произвольный текст или None. attachments — список (имя, путь), по умолчанию пустой.
    #[pyo3(signature = (chat_id, role, content, quote=None, reply_to=None, attachments=vec![]))]
    fn add_message(
        &self,
        chat_id: i64,
        role: String,
        content: String,
        quote: Option<String>,
        reply_to: Option<String>,
        attachments: Vec<(String, String)>,
    ) -> PyResult<i64> {
        self.inner
            .lock()
            .unwrap()
            .add_message_full(
                chat_id,
                &role,
                &content,
                quote.as_deref(),
                reply_to.as_deref(),
                &attachments,
            )
            .map_err(to_py_err)
    }

    fn update_message(&self, message_id: i64, content: String) -> PyResult<bool> {
        self.inner
            .lock()
            .unwrap()
            .update_message(message_id, &content)
            .map_err(to_py_err)
    }

    fn get_messages(&self, chat_id: i64) -> PyResult<Vec<PyMessage>> {
        self.inner
            .lock()
            .unwrap()
            .get_messages(chat_id)
            .map(|messages| messages.into_iter().map(PyMessage::from).collect())
            .map_err(to_py_err)
    }

    fn list_chats(&self) -> PyResult<Vec<(i64, String, i64)>> {
        self.inner.lock().unwrap().list_chats().map_err(to_py_err)
    }

    fn schema_version(&self) -> PyResult<i32> {
        self.inner.lock().unwrap().schema_version().map_err(to_py_err)
    }
}

/// Точка входа модуля для Python: `import advanced_xopilot` после сборки (`maturin develop` / `cargo build --release` + копирование .so/.pyd рядом с App/).
#[pymodule]
fn advanced_xopilot(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyDatabase>()?;
    m.add_class::<PyMessage>()?;
    Ok(())
}