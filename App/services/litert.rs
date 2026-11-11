// Описание: Официальный C API LiteRT-LM 1.0.0. Владение указателями ограничено RAII.
// ABI закреплён по v0.19.1/include/{engine,conversation}.h.
use anyhow::{Context, Result, bail, ensure};
use libloading::Library;
use serde_json::Value;
#[cfg(not(target_os = "android"))]
use sha2::{Digest, Sha256};
use std::{
    ffi::{CStr, CString, c_char, c_int, c_void},
    path::{Path, PathBuf},
    ptr,
    sync::{Mutex, OnceLock},
};
use tokio_util::sync::CancellationToken;
static ENGINE_LOADS: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
type Handle = *mut c_void;
type Callback = unsafe extern "C" fn(Handle, *const c_void);

macro_rules! api {
    ($($field:ident: $kind:ty => $symbol:literal),* $(,)?) => {
        struct Api { _library: Library, $($field: $kind),* }
        impl Api {
            /// Загружает закреплённые символы C API и удерживает библиотеку живой.
            unsafe fn load(path: &Path) -> Result<Self> {
                // Все функции копируются, но Library живёт дольше любого указателя.
                let library = unsafe { Library::new(path) }.context("Не удалось открыть LiteRT")?;
                $(let $field = unsafe { *library.get::<$kind>(concat!($symbol, "\0").as_bytes())? };)*
                Ok(Self { _library: library, $($field),* })
            }
        }
    }
}
api! {
    version: unsafe extern "C" fn(*mut c_int,*mut c_int,*mut c_int)->c_int => "litert_lm_get_api_version",
    error: unsafe extern "C" fn()->*const c_char => "litert_lm_get_last_error_message",
    settings: unsafe extern "C" fn(*const c_char,*const c_char,*const c_char,*const c_char,*mut Handle)->c_int => "litert_lm_engine_settings_create",
    settings_delete: unsafe extern "C" fn(Handle)->() => "litert_lm_engine_settings_delete",
    tokens: unsafe extern "C" fn(Handle,c_int)->c_int => "litert_lm_engine_settings_set_max_num_tokens",
    threads: unsafe extern "C" fn(Handle,c_int)->c_int => "litert_lm_engine_settings_set_num_threads",
    single_threaded: unsafe extern "C" fn(Handle,bool)->c_int => "litert_lm_engine_settings_set_single_threaded_execution",
    engine: unsafe extern "C" fn(Handle,*mut Handle)->c_int => "litert_lm_engine_create",
    engine_delete: unsafe extern "C" fn(Handle)->() => "litert_lm_engine_delete",
    config: unsafe extern "C" fn(*mut Handle)->c_int => "litert_lm_conversation_config_create",
    config_delete: unsafe extern "C" fn(Handle)->() => "litert_lm_conversation_config_delete",
    messages: unsafe extern "C" fn(Handle,*const c_char)->c_int => "litert_lm_conversation_config_set_messages",
    session: unsafe extern "C" fn(*mut Handle)->c_int => "litert_lm_session_config_create",
    session_delete: unsafe extern "C" fn(Handle)->() => "litert_lm_session_config_delete",
    output_tokens: unsafe extern "C" fn(Handle,c_int)->c_int => "litert_lm_session_config_set_max_output_tokens",
    set_session: unsafe extern "C" fn(Handle,Handle)->c_int => "litert_lm_conversation_config_set_session_config",
    conversation: unsafe extern "C" fn(Handle,Handle,*mut Handle)->c_int => "litert_lm_conversation_create",
    conversation_delete: unsafe extern "C" fn(Handle)->() => "litert_lm_conversation_delete",
    stream: unsafe extern "C" fn(Handle,*const c_char,*const c_char,*const c_void,Callback,Handle)->c_int => "litert_lm_conversation_send_message_stream",
    wait: unsafe extern "C" fn(Handle)->c_int => "litert_lm_conversation_wait_until_done",
    cancel: unsafe extern "C" fn(Handle)->c_int => "litert_lm_conversation_cancel_process",
    text: unsafe extern "C" fn(*const c_void,*mut *const c_char)->c_int => "litert_lm_stream_chunk_get_text",
    chunk_error: unsafe extern "C" fn(*const c_void,*mut *const c_char)->c_int => "litert_lm_stream_chunk_get_error",
    final_chunk: unsafe extern "C" fn(*const c_void,*mut bool)->c_int => "litert_lm_stream_chunk_is_final",
    sampler: unsafe extern "C" fn(c_int,*mut Handle)->c_int => "litert_lm_sampler_params_create",
    sampler_top_k: unsafe extern "C" fn(Handle,c_int)->c_int => "litert_lm_sampler_params_set_top_k",
    sampler_delete: unsafe extern "C" fn(Handle)->() => "litert_lm_sampler_params_delete",
    set_sampler: unsafe extern "C" fn(Handle,Handle)->c_int => "litert_lm_session_config_set_sampler_params",
    token_count: unsafe extern "C" fn(Handle,*mut usize)->c_int => "litert_lm_conversation_get_token_count",
}
impl Api {
    /// Преобразует статус C API в ошибку на том же worker-потоке.
    fn check(&self, code: c_int) -> Result<()> {
        if code == 0 {
            return Ok(());
        }
        // Последняя ошибка читается на том же worker-потоке, что и вызов C API.
        let error = unsafe { (self.error)() };
        let message = if error.is_null() {
            String::new()
        } else {
            unsafe { CStr::from_ptr(error) }
                .to_string_lossy()
                .into_owned()
        };
        bail!("LiteRT ({code}): {message}")
    }
}
struct Owned<'a> {
    pointer: Handle,
    delete: unsafe extern "C" fn(Handle),
    _api: &'a Api,
}
impl Owned<'_> {
    /// Передаёт владение указателем из RAII-guard в долгоживущий кеш.
    fn into_raw(self) -> Handle {
        let pointer = self.pointer;
        std::mem::forget(self);
        pointer
    }
}
impl Drop for Owned<'_> {
    /// Освобождает принадлежащие владельцу ресурсы в порядке RAII.
    fn drop(&mut self) {
        unsafe { (self.delete)(self.pointer) }
    }
}
/// Создаёт проверенный C-объект и связывает его с функцией освобождения.
fn owned(
    api: &Api,
    create: impl FnOnce(*mut Handle) -> c_int,
    delete: unsafe extern "C" fn(Handle),
) -> Result<Owned<'_>> {
    let mut pointer = ptr::null_mut();
    api.check(create(&mut pointer))?;
    ensure!(!pointer.is_null(), "LiteRT вернул пустой объект");
    Ok(Owned {
        pointer,
        delete,
        _api: api,
    })
}

#[cfg(not(target_os = "android"))]
const EMBEDDED: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/liblitert-lm.so"));
const NOTICES: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/runtime-licenses.zip"));
/// Проверяет, включён ли нативный runtime в данную сборку.
pub fn available() -> bool {
    env!("XOPILOT_LITERT_BUNDLED") == "1"
}
/// Возвращает упакованный runtime и сохраняет его лицензионные уведомления.
#[cfg(target_os = "android")]
fn library_path() -> Result<PathBuf> {
    ensure!(available(), "В APK отсутствует LiteRT");
    let root = super::paths::base_data_dir()?.join("runtime");
    std::fs::create_dir_all(&root)?;
    if !NOTICES.is_empty() {
        std::fs::write(root.join("runtime-licenses.zip"), NOTICES)?;
    }
    Ok(PathBuf::from("liblitert-lm.so"))
}
/// Возвращает упакованный runtime и сохраняет его лицензионные уведомления.
#[cfg(not(target_os = "android"))]
fn library_path() -> Result<PathBuf> {
    ensure!(
        available(),
        "Сборка без LiteRT. Разработчику: scripts/prepare_runtime.sh и повторная сборка"
    );
    let digest = hex::encode(Sha256::digest(EMBEDDED));
    let root = super::paths::base_data_dir()?
        .join("runtime")
        .join(&digest[..16]);
    std::fs::create_dir_all(&root)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(&root, std::fs::Permissions::from_mode(0o700))?;
    }
    let path = root.join(if cfg!(target_os = "windows") {
        "litert-lm.dll"
    } else {
        "liblitert-lm.so"
    });
    if !NOTICES.is_empty() {
        std::fs::write(root.join("runtime-licenses.zip"), NOTICES)?;
    }
    if !path.is_file()
        || super::model_installer::digest_file(&path, &CancellationToken::new())? != digest
    {
        use std::io::Write;
        let mut temporary = tempfile::NamedTempFile::new_in(&root)?;
        temporary.write_all(EMBEDDED)?;
        temporary.as_file().sync_all()?;
        // persist заменяет испорченный файл также на Windows, где обычный rename не заменяет DLL.
        temporary.persist(&path).map_err(|error| error.error)?;
    }
    Ok(path)
}

struct Engine {
    api: Api,
    engine: Handle,
    path: PathBuf,
    backend: String,
    cached: Option<CachedConversation>,
    statistics: ContextStats,
}
struct CachedConversation {
    pointer: Handle,
    config: Handle,
    session: Handle,
    sampler: Handle,
    history: Vec<Value>,
    images: tempfile::TempDir,
    output_limit: i32,
}
#[derive(Clone, Copy, Default, Debug)]
pub struct ContextStats {
    pub engine_loads: usize,
    pub reused: usize,
    pub rebuilt: usize,
    pub tokens: usize,
}
// C API допускает перенос handle между потоками, но не параллельные вызовы.
// Единственный Mutex ниже сериализует загрузку, генерацию и выгрузку.
unsafe impl Send for Engine {}
impl Drop for Engine {
    /// Освобождает принадлежащие владельцу ресурсы в порядке RAII.
    fn drop(&mut self) {
        self.clear_context();
        unsafe { (self.api.engine_delete)(self.engine) }
    }
}
impl Engine {
    /// Создаёт engine выбранного устройства с ограничением контекста и числа потоков.
    fn open(path: &Path, backend: &str) -> Result<Self> {
        let api = unsafe { Api::load(&library_path()?)? };
        let (mut major, mut minor, mut patch) = (0, 0, 0);
        api.check(unsafe { (api.version)(&mut major, &mut minor, &mut patch) })?;
        ensure!(
            major == 1,
            "Нужен LiteRT C API 1.x, найден {major}.{minor}.{patch}"
        );
        let filename = CString::new(path.to_string_lossy().as_bytes())?;
        let device = CString::new(backend)?;
        let settings = owned(
            &api,
            |out| unsafe {
                (api.settings)(
                    filename.as_ptr(),
                    device.as_ptr(),
                    c"cpu".as_ptr(),
                    ptr::null(),
                    out,
                )
            },
            api.settings_delete,
        )?;
        api.check(unsafe { (api.tokens)(settings.pointer, 4096) })?;
        let threads = std::thread::available_parallelism()
            .map(|n| n.get().min(6) as i32)
            .unwrap_or(2);
        api.check(unsafe { (api.threads)(settings.pointer, threads) })?;
        api.check(unsafe { (api.single_threaded)(settings.pointer, true) })?;
        let mut engine = ptr::null_mut();
        api.check(unsafe { (api.engine)(settings.pointer, &mut engine) })?;
        drop(settings);
        ensure!(!engine.is_null(), "Модель не загрузилась");
        Ok(Self {
            api,
            engine,
            path: path.to_owned(),
            backend: backend.into(),
            cached: None,
            statistics: ContextStats {
                engine_loads: ENGINE_LOADS.fetch_add(1, std::sync::atomic::Ordering::Relaxed) + 1,
                ..Default::default()
            },
        })
    }
    /// Освобождает conversation, конфигурации и временные изображения, сохраняя веса.
    fn clear_context(&mut self) {
        if let Some(cache) = self.cached.take() {
            unsafe {
                (self.api.conversation_delete)(cache.pointer);
                (self.api.config_delete)(cache.config);
                (self.api.session_delete)(cache.session);
                (self.api.sampler_delete)(cache.sampler);
            }
        }
        self.statistics.tokens = 0;
    }
    /// Выполняет запрос выбранной модели и возвращает итоговый текст.
    fn reply(
        &mut self,
        messages: Vec<Value>,
        token: CancellationToken,
        updates: tokio::sync::mpsc::UnboundedSender<String>,
        output_limit: i32,
    ) -> Result<String> {
        ensure!(!token.is_cancelled(), "Запрос отменён");
        ensure!(!messages.is_empty(), "Нет сообщения пользователя");
        let reusable = self.cached.as_ref().is_some_and(|cache| {
            cache.output_limit == output_limit && can_extend(&cache.history, &messages)
        });
        let suffix = if reusable {
            self.cached.as_ref().unwrap().history.len()
        } else {
            0
        };
        if !reusable {
            self.clear_context();
            let mut initial = messages.clone();
            let _last = initial.pop();
            let images = tempfile::tempdir()?;
            convert_images(&mut initial, images.path())?;
            let api = &self.api;
            let session = owned(api, |out| unsafe { (api.session)(out) }, api.session_delete)?;
            api.check(unsafe {
                (api.output_tokens)(session.pointer, output_limit.clamp(1, 2048))
            })?;
            // Top-K=1 снижает случайные изменения аргументов и лишних знаков в точных данных.
            let sampler = owned(
                api,
                |out| unsafe { (api.sampler)(2, out) },
                api.sampler_delete,
            )?;
            api.check(unsafe { (api.sampler_top_k)(sampler.pointer, 1) })?;
            api.check(unsafe { (api.set_sampler)(session.pointer, sampler.pointer) })?;
            let config = owned(api, |out| unsafe { (api.config)(out) }, api.config_delete)?;
            api.check(unsafe { (api.set_session)(config.pointer, session.pointer) })?;
            let history = CString::new(serde_json::to_string(&initial)?)?;
            api.check(unsafe { (api.messages)(config.pointer, history.as_ptr()) })?;
            let conversation = owned(
                api,
                |out| unsafe { (api.conversation)(self.engine, config.pointer, out) },
                api.conversation_delete,
            )?;
            let (pointer, config, session) = (
                conversation.into_raw(),
                config.into_raw(),
                session.into_raw(),
            );
            // Все конфигурации живут до уничтожения conversation, как и её изображения.
            // Передаём их из краткоживущих RAII-guard в единый кеш Engine.
            self.cached = Some(CachedConversation {
                pointer,
                config,
                session,
                sampler: sampler.into_raw(),
                history: Vec::new(),
                images,
                output_limit,
            });
        }
        let cache = self.cached.as_mut().unwrap();
        let mut new_messages = if reusable {
            messages[suffix..].to_vec()
        } else {
            vec![messages.last().unwrap().clone()]
        };
        convert_images(&mut new_messages, cache.images.path())?;
        let message = merge_new_messages(new_messages)?;
        let message = CString::new(serde_json::to_string(&message)?)?;
        let result = stream_reply(&self.api, cache.pointer, &message, token, updates);
        match result {
            Ok(answer) => {
                let cache = self.cached.as_mut().unwrap();
                cache.history = messages;
                cache
                    .history
                    .push(serde_json::json!({"role":"assistant","content":answer}));
                let mut tokens = 0;
                let _ = unsafe { (self.api.token_count)(cache.pointer, &mut tokens) };
                self.statistics.tokens = tokens;
                if reusable {
                    self.statistics.reused += 1;
                } else {
                    self.statistics.rebuilt += 1;
                }
                Ok(answer)
            }
            Err(error) => {
                self.clear_context();
                Err(error)
            }
        }
    }
}
/// Разрешает дополнение KV-кеша только для точного продолжения прежней истории.
pub fn can_extend(previous: &[Value], incoming: &[Value]) -> bool {
    incoming.len() > previous.len()
        && incoming.starts_with(previous)
        && incoming[previous.len()..]
            .iter()
            .all(|m| m["role"] == "user")
}
/// Объединяет новые пользовательские данные в один допустимый запрос LiteRT.
fn merge_new_messages(mut messages: Vec<Value>) -> Result<Value> {
    ensure!(!messages.is_empty(), "Нет новых данных для модели");
    if messages.len() == 1 {
        return Ok(messages.pop().unwrap());
    }
    let mut parts = Vec::new();
    for message in messages {
        if !parts.is_empty() {
            parts.push(serde_json::json!({"type":"text","text":"\n"}));
        }
        match &message["content"] {
            Value::String(text) => parts.push(serde_json::json!({"type":"text","text":text})),
            Value::Array(content) => parts.extend(content.clone()),
            _ => bail!("Неверное содержимое сообщения"),
        }
    }
    Ok(serde_json::json!({"role":"user","content":parts}))
}
/// Дожидается окончания callback перед освобождением потокового запроса.
fn stream_reply(
    api: &Api,
    conversation: Handle,
    message: &CString,
    token: CancellationToken,
    updates: tokio::sync::mpsc::UnboundedSender<String>,
) -> Result<String> {
    let mut context = Stream {
        api,
        conversation,
        token,
        updates,
        answer: String::new(),
        error: None,
    };
    api.check(unsafe {
        (api.stream)(
            conversation,
            message.as_ptr(),
            ptr::null(),
            ptr::null(),
            on_chunk,
            (&mut context as *mut Stream<'_>).cast(),
        )
    })?;
    // После cancel callback всё ещё может выполняться. Освобождаем данные лишь после wait.
    let code = unsafe { (api.wait)(conversation) };
    ensure!(!context.token.is_cancelled(), "Запрос отменён");
    api.check(code)?;
    if let Some(error) = context.error {
        bail!("{error}");
    }
    ensure!(
        !context.answer.trim().is_empty(),
        "Локальная модель вернула пустой ответ"
    );
    Ok(context.answer)
}
struct Stream<'a> {
    api: &'a Api,
    conversation: Handle,
    token: CancellationToken,
    updates: tokio::sync::mpsc::UnboundedSender<String>,
    answer: String,
    error: Option<String>,
}
/// Накапливает текст и обрабатывает отмену, не выпуская panic через C ABI.
unsafe extern "C" fn on_chunk(data: Handle, chunk: *const c_void) {
    // В single-threaded режиме callback вызывается только внутри wait этого worker.
    // Через FFI никогда не выпускаем panic.
    let _ = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        let context = unsafe { &mut *data.cast::<Stream<'_>>() };
        let mut is_final = false;
        unsafe {
            (context.api.final_chunk)(chunk, &mut is_final);
        }
        if (context.token.is_cancelled() || context.error.is_some()) && !is_final {
            unsafe {
                (context.api.cancel)(context.conversation);
            }
            return;
        }
        let mut error = ptr::null();
        let mut text = ptr::null();
        unsafe {
            (context.api.chunk_error)(chunk, &mut error);
            (context.api.text)(chunk, &mut text);
        }
        if !error.is_null() {
            context.error = Some(
                unsafe { CStr::from_ptr(error) }
                    .to_string_lossy()
                    .into_owned(),
            );
        }
        if !text.is_null() {
            let raw = unsafe { CStr::from_ptr(text) }
                .to_string_lossy()
                .into_owned();
            let text = match decode_chunk(&raw) {
                Ok(text) => text,
                Err(error) => {
                    context.error = Some(format!("{error:#}"));
                    return;
                }
            };
            if context.answer.len() + text.len() > 8 * 1024 * 1024 {
                context.error = Some("Ответ больше 8 МиБ".into());
                return;
            }
            context.answer.push_str(&text);
            let _ = context.updates.send(text);
        }
    }));
}
/// Conversation API передаёт JSON-сообщение, а не готовую строку токена.
pub fn decode_chunk(raw: &str) -> Result<String> {
    let value: Value = serde_json::from_str(raw).context("Неверный JSON-чанк LiteRT")?;
    if let Some(content) = value["content"].as_str() {
        return Ok(content.into());
    }
    Ok(value["content"]
        .as_array()
        .map(|parts| {
            parts
                .iter()
                .filter(|part| part["type"] == "text")
                .filter_map(|part| part["text"].as_str())
                .collect::<String>()
        })
        .unwrap_or_default())
}

/// Заменяет подготовленные JPEG-данные временными файлами для LiteRT.
fn convert_images(messages: &mut [Value], root: &Path) -> Result<()> {
    use base64::Engine as _;
    for message in messages {
        if let Some(parts) = message["content"].as_array_mut() {
            for part in parts {
                if part["type"] == "image_url" {
                    let data = part["image_url"]["url"]
                        .as_str()
                        .and_then(|url| url.strip_prefix("data:image/jpeg;base64,"))
                        .context("Локальная модель принимает только подготовленные изображения")?;
                    let bytes = base64::prelude::BASE64_STANDARD.decode(data)?;
                    ensure!(
                        bytes.len() <= super::attachments::MAX_FILE_BYTES as usize,
                        "Слишком большое изображение"
                    );
                    let path = root.join(format!("{}.jpg", uuid::Uuid::new_v4()));
                    std::fs::write(&path, bytes)?;
                    *part = serde_json::json!({"type":"image","path":path});
                }
            }
        }
    }
    Ok(())
}
static ENGINE: OnceLock<Mutex<Option<Engine>>> = OnceLock::new();
/// Не пересчитываем свободную VRAM для уже загруженной модели: её память уже занята нами.
pub fn loaded_backend(path: &Path) -> Option<String> {
    ENGINE
        .get()?
        .try_lock()
        .ok()?
        .as_ref()
        .filter(|engine| engine.path == path)
        .map(|engine| engine.backend.clone())
}
/// Сбрасывает conversation при смене чата, не выгружая веса модели.
pub fn reset_context() -> Result<()> {
    let mut engine = ENGINE
        .get_or_init(|| Mutex::new(None))
        .try_lock()
        .map_err(|_| anyhow::anyhow!("Модель сейчас отвечает"))?;
    if let Some(engine) = engine.as_mut() {
        engine.clear_context();
    }
    Ok(())
}
/// Возвращает фактическое число дополнений, пересозданий и токенов кеша.
pub fn context_stats() -> Result<ContextStats> {
    let engine = ENGINE
        .get_or_init(|| Mutex::new(None))
        .try_lock()
        .map_err(|_| anyhow::anyhow!("Модель сейчас отвечает"))?;
    Ok(engine.as_ref().map(|e| e.statistics).unwrap_or_default())
}
/// Освобождает engine, кеш и память выбранной локальной модели.
pub fn unload() -> Result<()> {
    let mut engine = ENGINE
        .get_or_init(|| Mutex::new(None))
        .try_lock()
        .map_err(|_| anyhow::anyhow!("Модель сейчас отвечает"))?;
    *engine = None;
    Ok(())
}
/// Сериализует обращения к одному engine и повторно использует подходящий контекст.
pub fn generate(
    path: PathBuf,
    backend: String,
    messages: Vec<Value>,
    token: CancellationToken,
    updates: tokio::sync::mpsc::UnboundedSender<String>,
    output_limit: i32,
) -> Result<String> {
    ensure!(!token.is_cancelled(), "Запрос отменён");
    let mut engine = ENGINE
        .get_or_init(|| Mutex::new(None))
        .lock()
        .map_err(|_| anyhow::anyhow!("Ошибка состояния модели"))?;
    if engine
        .as_ref()
        .is_none_or(|item| item.path != path || item.backend != backend)
    {
        *engine = None;
        *engine = Some(Engine::open(&path, &backend)?);
    }
    engine
        .as_mut()
        .unwrap()
        .reply(messages, token, updates, output_limit)
}

#[cfg(test)]
mod chunk_tests {
    /// Проверяет извлечение текста без JSON-оболочки и скрытых рассуждений.
    #[test]
    fn conversation_chunks_expose_text_instead_of_the_json_envelope() {
        assert_eq!(super::decode_chunk(r#"{"role":"assistant","content":[{"type":"text","text":"Привет"},{"type":"text","text":"!"}]}"#).unwrap(),"Привет!");
        assert_eq!(
            super::decode_chunk(r#"{"content":[{"type":"thought","text":"internal"}]}"#).unwrap(),
            ""
        );
        assert!(super::decode_chunk("{broken").is_err());
    }
}
