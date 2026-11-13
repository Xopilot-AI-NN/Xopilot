// Описание: Android DownloadManager сохраняет загрузку и уведомление независимо от процесса UI.
// Rust не пытается удерживать Activity или поток интерфейса живым ради сетевого запроса.
// В файл сохраняем квитанцию ОС, а после перезапуска снова читаем ту же задачу по ID.
// Успех DownloadManager означает только доставку: право выбрать модель появляется после SHA-256.
use super::{
    android::with_context,
    model_installer::{Model, Progress},
};
use anyhow::{Result, ensure};
use jni::{
    Env, jni_sig, jni_str,
    objects::{JObject, JString, JValue},
};
use serde::{Deserialize, Serialize};
use std::{
    collections::{HashMap, HashSet},
    path::PathBuf,
    sync::{
        Mutex, OnceLock,
        atomic::{AtomicBool, Ordering},
    },
};

#[derive(Default)]
struct State {
    tickets: HashMap<String, i64>,
    progress: HashMap<String, Progress>,
    verifying: HashSet<String>,
}
static STATE: OnceLock<Mutex<State>> = OnceLock::new();
static MONITOR: AtomicBool = AtomicBool::new(false);

/// Только ID системных загрузок сохраняются на диске; содержимое чатов сюда не попадает.
fn state() -> &'static Mutex<State> {
    STATE.get_or_init(|| {
        let tickets = metadata()
            .ok()
            .and_then(|p| std::fs::read(p).ok())
            .filter(|b| b.len() <= 16_384)
            .and_then(|b| {
                serde_json::from_slice::<
                        HashMap<String, i64>,
                    >(&b)
                    .ok()
            })
            .unwrap_or_default();
        Mutex::new(State {
            tickets,
            ..Default::default()
        })
    })
}
/// Выбирает метаданные возобновления рядом с каталогом весов.
fn metadata() -> Result<PathBuf> {
    Ok(super::paths::models_dir()?
        .join("android-downloads.json"))
}
/// Заменяет метаданные атомарно, чтобы выключение процесса не теряло системный ID.
fn save(value: &State) -> Result<()> {
    use std::io::Write;
    let path = metadata()?;
    std::fs::create_dir_all(path.parent().unwrap())?;
    let mut temporary = tempfile::NamedTempFile::new_in(
        path.parent().unwrap(),
    )?;
    temporary
        .write_all(&serde_json::to_vec(&value.tickets)?)?;
    temporary.as_file().sync_all()?;
    temporary.persist(path).map_err(|e| e.error)?;
    Ok(())
}
/// Возвращает Android-сервис через Application Context, без отдельного Java/Kotlin сервиса.
fn manager<'a>(
    env: &mut Env<'a>,
    activity: &JObject<'_>,
) -> Result<JObject<'a>> {
    let name = env.new_string("download")?;
    let service = env
        .call_method(
            activity,
            jni_str!("getSystemService"),
            jni_sig!(
                "(Ljava/lang/String;)Ljava/lang/Object;"
            ),
            &[JValue::Object(&name)],
        )?
        .l()?;
    ensure!(
        !service.is_null(),
        "На этом Android недоступен системный загрузчик"
    );
    Ok(service)
}
/// App-specific external storage доступен DownloadManager без разрешения на все файлы.
fn staging(spec: Model) -> Result<PathBuf> {
    with_context(|env, activity| {
        let file = env
            .call_method(
                &activity,
                jni_str!("getExternalFilesDir"),
                jni_sig!(
                    "(Ljava/lang/String;)Ljava/io/File;"
                ),
                &[JValue::Object(&JObject::null())],
            )?
            .l()?;
        ensure!(
            !file.is_null(),
            "Android не предоставил каталог загрузки"
        );
        let path = env
            .call_method(
                file,
                jni_str!("getAbsolutePath"),
                jni_sig!("()Ljava/lang/String;"),
                &[],
            )?
            .l()?;
        let path = JString::cast_local(env, path)?
            .try_to_string(env)?;
        Ok(PathBuf::from(path)
            .join("models")
            .join(format!("{}.download", spec.filename)))
    })
}
/// Ставит публичный URL модели в системную очередь с постоянным уведомлением о прогрессе.
fn enqueue(spec: Model) -> Result<i64> {
    let destination = staging(spec)?;
    std::fs::create_dir_all(destination.parent().unwrap())?;
    if destination.exists() {
        std::fs::remove_file(&destination)?;
    }
    with_context(|env, activity| {
        let url = env.new_string(
            super::model_updates::source(spec)?.0,
        )?;
        let uri = env
            .call_static_method(
                jni_str!("android/net/Uri"),
                jni_str!("parse"),
                jni_sig!(
                    "(Ljava/lang/String;)Landroid/net/Uri;"
                ),
                &[JValue::Object(&url)],
            )?
            .l()?;
        let request = env.new_object(
            jni_str!("android/app/DownloadManager$Request"),
            jni_sig!("(Landroid/net/Uri;)V"),
            &[JValue::Object(&uri)],
        )?;
        let title = env.new_string(format!(
            "Xopilot · {}",
            spec.name
        ))?;
        env.call_method(
            &request,
            jni_str!("setTitle"),
            jni_sig!("(Ljava/lang/CharSequence;)Landroid/app/DownloadManager$Request;"),
            &[JValue::Object(&title)],
        )?;
        let description = env.new_string("Загрузка модели · SHA-256 будет проверен в Xopilot")?;
        env.call_method(
            &request,
            jni_str!("setDescription"),
            jni_sig!("(Ljava/lang/CharSequence;)Landroid/app/DownloadManager$Request;"),
            &[JValue::Object(&description)],
        )?;
        env.call_method(
            &request,
            jni_str!("setNotificationVisibility"),
            jni_sig!(
                "(I)Landroid/app/DownloadManager$Request;"
            ),
            &[JValue::Int(1)],
        )?;
        let file_uri = env.new_string(format!(
            "file://{}",
            destination.display()
        ))?;
        // setDestinationUri принимает файл в app-specific каталоге и не требует STORAGE permission.
        let uri = env
            .call_static_method(
                jni_str!("android/net/Uri"),
                jni_str!("parse"),
                jni_sig!(
                    "(Ljava/lang/String;)Landroid/net/Uri;"
                ),
                &[JValue::Object(&file_uri)],
            )?
            .l()?;
        env.call_method(
            &request,
            jni_str!("setDestinationUri"),
            jni_sig!("(Landroid/net/Uri;)Landroid/app/DownloadManager$Request;"),
            &[JValue::Object(&uri)],
        )?;
        let manager = manager(env, &activity)?;
        Ok(env
            .call_method(
                manager,
                jni_str!("enqueue"),
                jni_sig!("(Landroid/app/DownloadManager$Request;)J"),
                &[JValue::Object(&request)],
            )?
            .j()?)
    })
}

#[derive(Serialize, Deserialize)]
struct Status {
    status: i32,
    bytes: u64,
    total: Option<u64>,
    reason: i32,
}
/// Читает одну строку системного реестра; Cursor закрывается также при ошибке столбца.
fn query(id: i64) -> Result<Option<Status>> {
    with_context(|env, activity| {
        let filter = env.new_long_array(1)?;
        filter.set_region(env, 0, &[id])?;
        let query = env.new_object(
            jni_str!("android/app/DownloadManager$Query"),
            jni_sig!("()V"),
            &[],
        )?;
        env.call_method(
            &query,
            jni_str!("setFilterById"),
            jni_sig!(
                "([J)Landroid/app/DownloadManager$Query;"
            ),
            &[JValue::Object(&filter)],
        )?;
        let manager = manager(env, &activity)?;
        let cursor = env
            .call_method(
                manager,
                jni_str!("query"),
                jni_sig!("(Landroid/app/DownloadManager$Query;)Landroid/database/Cursor;"),
                &[JValue::Object(&query)],
            )?
            .l()?;
        ensure!(
            !cursor.is_null(),
            "Android не предоставил состояние загрузки"
        );
        let result = (|| -> Result<Option<Status>> {
            if !env
                .call_method(
                    &cursor,
                    jni_str!("moveToFirst"),
                    jni_sig!("()Z"),
                    &[],
                )?
                .z()?
            {
                return Ok(None);
            }
            let mut get = |name: &str| -> Result<i64> {
                let name = env.new_string(name)?;
                let column = env
                    .call_method(
                        &cursor,
                        jni_str!("getColumnIndexOrThrow"),
                        jni_sig!("(Ljava/lang/String;)I"),
                        &[JValue::Object(&name)],
                    )?
                    .i()?;
                Ok(env
                    .call_method(
                        &cursor,
                        jni_str!("getLong"),
                        jni_sig!("(I)J"),
                        &[JValue::Int(column)],
                    )?
                    .j()?)
            };
            let total = get("total_size")?;
            Ok(Some(Status {
                status: get("status")? as i32,
                bytes: get("bytes_so_far")?.max(0) as u64,
                total: (total > 0).then_some(total as u64),
                reason: get("reason")? as i32,
            }))
        })();
        let _ = env.call_method(
            cursor,
            jni_str!("close"),
            jni_sig!("()V"),
            &[],
        );
        result
    })
}
/// Удаляет только принадлежащую приложению системную задачу; Android очищает её временный файл.
fn remove_system(id: i64) -> Result<()> {
    with_context(|env, activity| {
        let ids = env.new_long_array(1)?;
        ids.set_region(env, 0, &[id])?;
        let manager = manager(env, &activity)?;
        env.call_method(
            manager,
            jni_str!("remove"),
            jni_sig!("([J)I"),
            &[JValue::Object(&ids)],
        )?;
        Ok(())
    })
}
/// Возвращает сохранённый прогресс без JNI/диска на каждом перерисовывании карточки.
pub fn progress(id: &str) -> Option<Progress> {
    let value = state().lock().ok()?;
    value.progress.get(id).cloned().or_else(|| {
        value.tickets.contains_key(id).then(|| Progress {
            phase: "downloading".into(),
            ..Default::default()
        })
    })
}
/// Продолжение уже поставленной задачи не создаёт вторую многогигабайтную загрузку.
pub fn start(spec: Model) -> Result<()> {
    let existing = state()
        .lock()
        .map_err(|_| {
            anyhow::anyhow!("Реестр загрузок занят")
        })?
        .tickets
        .get(spec.id)
        .copied();
    if let Some(id) = existing {
        if query(id)?.is_some_and(|s| s.status != 16) {
            ensure_monitor();
            return Ok(());
        }
        let _ = remove_system(id);
    }
    let id = enqueue(spec)?;
    let result = (|| {
        let mut value = state().lock().map_err(|_| {
            anyhow::anyhow!("Реестр загрузок занят")
        })?;
        value.tickets.insert(spec.id.into(), id);
        value.progress.insert(
            spec.id.into(),
            Progress {
                phase: "downloading".into(),
                ..Default::default()
            },
        );
        save(&value)
    })();
    if result.is_err() {
        let _ = remove_system(id);
    }
    result?;
    ensure_monitor();
    Ok(())
}
/// Явная отмена отличается от паузы: DownloadManager не предоставляет публичной ручной паузы.
pub fn cancel(id: &str) -> Result<()> {
    // Держим один guard от проверки до удаления квитанции. Иначе monitor может
    // начать SHA-проверку между двумя lock(), а отмена удалит читаемый им файл.
    // Системный remove короткий; многогигабайтное копирование под mutex не идёт.
    let mut value = state().lock().map_err(|_| {
        anyhow::anyhow!("Реестр загрузок занят")
    })?;
    ensure!(
        !value.verifying.contains(id),
        "Дождитесь окончания проверки модели"
    );
    if let Some(ticket) = value.tickets.get(id).copied() {
        remove_system(ticket)?;
    }
    value.tickets.remove(id);
    value.progress.remove(id);
    save(&value)
}
/// Завершает проверенный файл в каталоге моделей; копирование и хеш идут только в worker.
fn install(spec: Model) -> Result<()> {
    let source = staging(spec)?;
    super::model_installer::import(spec, &source)
}
/// Восстанавливает наблюдение после перезапуска процесса. Само скачивание ведёт ОС.
pub fn ensure_monitor() {
    if MONITOR.swap(true, Ordering::AcqRel) {
        return;
    }
    super::runtime::runtime().spawn(async {
        loop {
            let tickets = state()
                .lock()
                .map(|s| s.tickets.clone())
                .unwrap_or_default();
            for (id, ticket) in tickets {
                let Ok(spec) = super::model_installer::model(&id) else {
                    continue;
                };
                let checking = state()
                    .lock()
                    .map(|s| s.verifying.contains(&id))
                    .unwrap_or(true);
                if checking {
                    continue;
                }
                let result = query(ticket);
                let status = match result {
                    Ok(Some(s)) => s,
                    Ok(None) => Status {
                        status: 16,
                        bytes: 0,
                        total: None,
                        reason: 0,
                    },
                    Err(error) => {
                        tracing::warn!("Не удалось прочитать DownloadManager: {error:#}");
                        continue;
                    }
                };
                let phase = match status.status {
                    8 => "verifying",
                    16 => "error",
                    4 => "waiting",
                    _ => "downloading",
                };
                if let Ok(mut value) = state().lock() {
                    // Отмена могла прийти, пока ContentProvider возвращал снимок.
                    // Устаревший ответ не должен воскресить отменённую карточку или установить файл.
                    if value.tickets.get(&id) != Some(&ticket) {
                        continue;
                    }
                    value.progress.insert(
                        id.clone(),
                        Progress {
                            phase: phase.into(),
                            downloaded: status.bytes,
                            total: status.total,
                            error: if status.status == 16 {
                                format!(
                                    "Android не завершил загрузку (код {}). Повторите скачивание.",
                                    status.reason
                                )
                            } else {
                                String::new()
                            },
                        },
                    );
                    if status.status == 8 {
                        value.verifying.insert(id.clone());
                    }
                }
                if status.status == 8 {
                    let result = super::runtime::blocking(move || install(spec)).await;
                    let mut value = state().lock().expect("DownloadManager state");
                    value.verifying.remove(&id);
                    match result {
                        Ok(()) => {
                            let _ = remove_system(ticket);
                            value.tickets.remove(&id);
                            value.progress.insert(
                                id,
                                Progress {
                                    phase: "installed".into(),
                                    downloaded: status.bytes,
                                    total: status.total,
                                    error: String::new(),
                                },
                            );
                            if let Err(error) = save(&value) {
                                tracing::warn!("{error:#}");
                            }
                        }
                        Err(error) => {
                            // Ошибочный файл не становится моделью; квитанция удаляется, ошибка остаётся в UI.
                            let _ = remove_system(ticket);
                            value.tickets.remove(&id);
                            value.progress.insert(
                                id,
                                Progress {
                                    phase: "error".into(),
                                    downloaded: status.bytes,
                                    total: status.total,
                                    error: format!("{error:#}"),
                                },
                            );
                            let _ = save(&value);
                        }
                    }
                }
            }
            tokio::time::sleep(std::time::Duration::from_secs(1)).await;
        }
    });
}
