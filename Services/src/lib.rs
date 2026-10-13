// Файл: Services/src/lib.rs
// Проект: Xopilot AI+ NN+
// Разработчик: DenBroLiik
// Версия: 1.0.0
// Описание: Rust-библиотека (cdylib) с PyO3-биндингом для Flet/Python UI.
//              Шифрование — всегда включено, ключ берётся автоматически из OS keyring (security::get_or_create_db_key).
//              cloud_sync / mcp / updates — заглушки под фазу 2.
//              Рабочий ИИ больше НЕ здесь — переехали на LiteRT-LM (App/services/llm.py, чистый Python).

#[cfg(feature = "sentiment")]
mod ai;
mod cloud_sync;
mod db;
mod mcp;
mod security;
mod updates;

#[cfg(feature = "sentiment")]
use ai::SentimentClassifier;
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
    inner: Mutex<Option<Database>>,
}

#[pymethods]
impl PyDatabase {
    /// Android supplies a random key unwrapped by Android Keystore. Desktop
    /// callers may keep using the existing system key resolver.
    #[new]
    #[pyo3(signature = (path, key=None))]
    fn new(path: String, key: Option<String>) -> PyResult<Self> {
        let db_path = std::path::PathBuf::from(&path);
        let fallback_dir = db_path
            .parent()
            .map(|p| p.to_path_buf())
            .unwrap_or_else(|| std::path::PathBuf::from("."));

        let existing = db_path.metadata().map(|m| m.len() > 0).unwrap_or(false);
        let keys = if let Some(key) = key {
            if key.len() != 64 || !key.bytes().all(|c| c.is_ascii_hexdigit()) {
                return Err(PyRuntimeError::new_err("Ключ БД должен содержать 32 байта в hex-формате."));
            }
            vec![key]
        } else {
            security::get_db_keys(&fallback_dir, existing).map_err(PyRuntimeError::new_err)?
        };
        let mut last_error = None;
        for key in keys {
            match Database::open(&path, &key) {
                Ok(db) => return Ok(PyDatabase { inner: Mutex::new(Some(db)) }),
                Err(error) => last_error = Some(error),
            }
        }
        Err(to_py_err(last_error.expect("key resolver returned no keys")))
    }

    /// Close deterministically even when UI callbacks still retain this object.
    fn close(&self) {
        self.inner.lock().unwrap().take();
    }

    fn __enter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __exit__(&self, _ty: &Bound<'_, PyAny>, _value: &Bound<'_, PyAny>, _trace: &Bound<'_, PyAny>) {
        self.close();
    }

    fn set_setting(&self, key: String, value: String) -> PyResult<()> {
        self.inner.lock().unwrap().as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?
            .set_setting(&key, &value)
            .map_err(to_py_err)
    }

    fn get_setting(&self, key: String) -> PyResult<Option<String>> {
        self.inner.lock().unwrap().as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?.get_setting(&key).map_err(to_py_err)
    }

    fn all_settings(&self) -> PyResult<Vec<(String, String, i64)>> {
        self.inner.lock().unwrap().as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?.all_settings().map_err(to_py_err)
    }

    fn create_chat(&self, title: String) -> PyResult<i64> {
        self.inner.lock().unwrap().as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?.create_chat(&title).map_err(to_py_err)
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
        self.inner.lock().unwrap().as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?
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

    #[pyo3(signature = (message_id, content, attachments=None))]
    fn update_message(&self, message_id: i64, content: String, attachments: Option<Vec<(String, String)>>) -> PyResult<bool> {
        let guard = self.inner.lock().unwrap();
        let database = guard.as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?;
        match attachments {
            Some(items) => database.update_message_full(message_id, &content, &items),
            None => database.update_message(message_id, &content),
        }.map_err(to_py_err)
    }

    fn delete_message(&self, message_id: i64) -> PyResult<bool> {
        self.inner.lock().unwrap().as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?.delete_message(message_id).map_err(to_py_err)
    }

    /// Удаляет чат целиком (сообщения и вложения — каскадно через FK на стороне SQLite).
    fn delete_chat(&self, chat_id: i64) -> PyResult<bool> {
        self.inner.lock().unwrap().as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?.delete_chat(chat_id).map_err(to_py_err)
    }

    fn get_messages(&self, chat_id: i64) -> PyResult<Vec<PyMessage>> {
        self.inner.lock().unwrap().as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?
            .get_messages(chat_id)
            .map(|messages| messages.into_iter().map(PyMessage::from).collect())
            .map_err(to_py_err)
    }

    fn list_chats(&self) -> PyResult<Vec<(i64, String, i64)>> {
        self.inner.lock().unwrap().as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?.list_chats().map_err(to_py_err)
    }

    fn rename_chat(&self, chat_id: i64, title: String) -> PyResult<bool> {
        self.inner.lock().unwrap().as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?.rename_chat(chat_id, &title).map_err(to_py_err)
    }

    fn list_chat_summaries(&self) -> PyResult<Vec<(i64, String, i64)>> {
        self.inner.lock().unwrap().as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?.list_chat_summaries().map_err(to_py_err)
    }

    fn sync_chat_snapshot(&self, chat_id: i64) -> PyResult<Option<String>> {
        self.inner.lock().unwrap().as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?.sync_chat_snapshot(chat_id).map_err(to_py_err)
    }
    #[pyo3(signature=(chat_id, expected, payload, ledger_key, ledger))]
    fn apply_sync_chat(&self, chat_id: Option<i64>, expected: Option<String>, payload: Option<String>, ledger_key: String, ledger: String) -> PyResult<Option<i64>> {
        self.inner.lock().unwrap().as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?.apply_sync_chat(chat_id,expected.as_deref(),payload.as_deref(),&ledger_key,&ledger).map_err(to_py_err)
    }
    fn apply_sync_settings(&self, expected: Vec<(String,Option<String>)>, updates: Vec<(String,String)>) -> PyResult<bool> {
        self.inner.lock().unwrap().as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?.apply_sync_settings(&expected,&updates).map_err(to_py_err)
    }

    fn schema_version(&self) -> PyResult<i32> {
        self.inner.lock().unwrap().as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?.schema_version().map_err(to_py_err)
    }

    fn total_message_count(&self) -> PyResult<i64> {
        self.inner.lock().unwrap().as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?.total_message_count().map_err(to_py_err)
    }

    fn clear_chat_messages(&self, chat_id: i64) -> PyResult<()> {
        self.inner.lock().unwrap().as_ref().ok_or_else(|| PyRuntimeError::new_err("База данных закрыта"))?.clear_chat_messages(chat_id).map_err(to_py_err)
    }
}

/// Python-обёртка над тестовым ONNX-классификатором тональности (пункт 5 плана).
#[pyclass]
#[cfg(feature = "sentiment")]
struct PySentimentClassifier {
    inner: SentimentClassifier,
}

#[pymethods]
#[cfg(feature = "sentiment")]
impl PySentimentClassifier {
    #[new]
    fn new(model_path: String) -> PyResult<Self> {
        let inner = SentimentClassifier::load(&model_path)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        Ok(PySentimentClassifier { inner })
    }

    /// Возвращает (метка_класса, уверенность): "negative"/"neutral"/"positive".
    fn classify(&self, text: String) -> PyResult<(String, f32)> {
        self.inner
            .classify(&text)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
}

/// Точка входа модуля для Python: `import advanced_xopilot` после сборки (`maturin develop` / `cargo build --release` + копирование .so/.pyd рядом с App/).
#[pymodule]
fn advanced_xopilot(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyDatabase>()?;
    m.add_class::<PyMessage>()?;
    #[cfg(feature = "sentiment")]
    m.add_class::<PySentimentClassifier>()?;
    Ok(())
}
