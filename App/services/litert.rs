// Описание: Официальный C API LiteRT-LM 1.0.0. Владение указателями ограничено RAII.
// ABI закреплён по v0.19.1/include/{engine,conversation}.h, не Python-обёртка.
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
type Handle = *mut c_void;
type Callback = unsafe extern "C" fn(Handle, *const c_void);

macro_rules! api {
    ($($field:ident: $kind:ty => $symbol:literal),* $(,)?) => {
        struct Api { _library: Library, $($field: $kind),* }
        impl Api {
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
}
impl Api {
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
impl Drop for Owned<'_> {
    fn drop(&mut self) {
        unsafe { (self.delete)(self.pointer) }
    }
}
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
pub fn available() -> bool {
    env!("XOPILOT_LITERT_BUNDLED") == "1"
}
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
    let path = root.join("liblitert-lm.so");
    if !NOTICES.is_empty() {
        std::fs::write(root.join("runtime-licenses.zip"), NOTICES)?;
    }
    if !path.is_file()
        || super::model_installer::digest_file(&path, &CancellationToken::new())? != digest
    {
        let temporary = root.join(format!("{}.tmp", uuid::Uuid::new_v4()));
        std::fs::write(&temporary, EMBEDDED)?;
        std::fs::rename(temporary, &path)?;
    }
    Ok(path)
}

struct Engine {
    api: Api,
    engine: Handle,
    path: PathBuf,
    backend: String,
}
// C API допускает перенос handle между потоками, но не параллельные вызовы.
// Единственный Mutex ниже сериализует загрузку, генерацию и выгрузку.
unsafe impl Send for Engine {}
impl Drop for Engine {
    fn drop(&mut self) {
        unsafe { (self.api.engine_delete)(self.engine) }
    }
}
impl Engine {
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
        })
    }
    fn reply(
        &self,
        mut messages: Vec<Value>,
        token: CancellationToken,
        updates: tokio::sync::mpsc::UnboundedSender<String>,
        output_limit: i32,
    ) -> Result<String> {
        ensure!(!token.is_cancelled(), "Запрос отменён");
        // C API читает изображения по пути; временные JPEG живут до конца prefill/stream.
        let image_root = tempfile::tempdir()?;
        convert_images(&mut messages, image_root.path())?;
        let last = messages.pop().context("Нет сообщения пользователя")?;
        let history = CString::new(serde_json::to_string(&messages)?)?;
        let message = CString::new(serde_json::to_string(&last)?)?;
        let api = &self.api;
        let session = owned(api, |out| unsafe { (api.session)(out) }, api.session_delete)?;
        api.check(unsafe { (api.output_tokens)(session.pointer, output_limit.clamp(1, 2048)) })?;
        let config = owned(api, |out| unsafe { (api.config)(out) }, api.config_delete)?;
        api.check(unsafe { (api.set_session)(config.pointer, session.pointer) })?;
        api.check(unsafe { (api.messages)(config.pointer, history.as_ptr()) })?;
        let conversation = owned(
            api,
            |out| unsafe { (api.conversation)(self.engine, config.pointer, out) },
            api.conversation_delete,
        )?;
        let mut context = Stream {
            api,
            conversation: conversation.pointer,
            token,
            updates,
            answer: String::new(),
            error: None,
        };
        api.check(unsafe {
            (api.stream)(
                conversation.pointer,
                message.as_ptr(),
                ptr::null(),
                ptr::null(),
                on_chunk,
                (&mut context as *mut Stream<'_>).cast(),
            )
        })?;
        // Даже при отмене ждём завершения callback перед освобождением context/изображений.
        let result = unsafe { (api.wait)(conversation.pointer) };
        ensure!(!context.token.is_cancelled(), "Запрос отменён");
        api.check(result)?;
        if let Some(error) = context.error {
            bail!("{error}");
        }
        ensure!(
            !context.answer.trim().is_empty(),
            "Локальная модель вернула пустой ответ"
        );
        Ok(context.answer)
    }
}
struct Stream<'a> {
    api: &'a Api,
    conversation: Handle,
    token: CancellationToken,
    updates: tokio::sync::mpsc::UnboundedSender<String>,
    answer: String,
    error: Option<String>,
}
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

#[cfg(test)]
mod chunk_tests {
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
pub fn unload() -> Result<()> {
    let mut engine = ENGINE
        .get_or_init(|| Mutex::new(None))
        .try_lock()
        .map_err(|_| anyhow::anyhow!("Модель сейчас отвечает"))?;
    *engine = None;
    Ok(())
}
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
        .as_ref()
        .unwrap()
        .reply(messages, token, updates, output_limit)
}
