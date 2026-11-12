// Файл: App/services/android.rs
// Описание: Android Context и Keystore через JNI, без Flutter-моста.
// Alias и SharedPreferences совпадают с прежним приложением.
use anyhow::{Context, Result, bail, ensure};
use base64::{Engine, prelude::BASE64_STANDARD};
use jni::{
    Env, JavaVM, jni_sig, jni_str,
    objects::{JByteArray, JObject, JString, JValue},
};
use std::path::{Path, PathBuf};

/// Подключает текущий поток к Android JVM на время JNI-вызова.
pub(crate) fn with_context<T>(
    call: impl FnOnce(&mut Env<'_>, JObject<'_>) -> Result<T>,
) -> Result<T> {
    let context = ndk_context::android_context();
    // VM и Activity принадлежат Dioxus/wry и живут до завершения Activity.
    let vm = unsafe { JavaVM::from_raw(context.vm().cast()) };
    vm.attach_current_thread(|env| {
        let result = env.with_local_frame(96, |env| {
            // Activity — глобальная ссылка Tao. Создаём собственную локальную
            // ссылку перед передачей владения JObject в текущий JNI frame.
            let raw_env = env.get_raw();
            let local =
                unsafe { ((**raw_env).v1_2.NewLocalRef)(raw_env, context.context().cast()) };
            ensure!(!local.is_null(), "Не удалось получить Android Activity");
            let activity = unsafe { JObject::from_raw(env, local) };
            call(env, activity)
        });
        if env.exception_check() {
            env.exception_clear();
        }
        result
    })
}

/// Сворачивает корневую задачу вместо уничтожения Activity и процесса Dioxus по кнопке «Назад».
pub fn move_to_background() -> Result<()> {
    with_context(|env, activity| {
        env.call_method(
            activity,
            jni_str!("moveTaskToBack"),
            jni_sig!("(Z)Z"),
            &[JValue::Bool(true)],
        )?;
        Ok(())
    })
}

/// Отмечает готовый интерфейс после кадра и шрифтов для честного Android startup timing.
pub fn report_fully_drawn() -> Result<()> {
    with_context(|env, activity| {
        env.call_method(activity, jni_str!("reportFullyDrawn"), jni_sig!("()V"), &[])?;
        Ok(())
    })
}

/// Преобразует Java String в Rust с проверкой JNI-ошибок.
fn java_string(env: &mut Env<'_>, object: JObject<'_>) -> Result<Option<String>> {
    if object.is_null() {
        return Ok(None);
    }
    let string = JString::cast_local(env, object)?;
    Ok(Some(string.try_to_string(env)?))
}

#[derive(Clone, Copy, Default, PartialEq, serde::Serialize)]
pub struct WindowInsets {
    pub top: i32,
    pub right: i32,
    pub bottom: i32,
    pub left: i32,
}

/// Читает реальные системные отступы окна; не подменяет их фиксированными dp.
pub fn window_insets() -> Result<Option<WindowInsets>> {
    with_context(|env, activity| {
        let window = env
            .call_method(
                &activity,
                jni_str!("getWindow"),
                jni_sig!("()Landroid/view/Window;"),
                &[],
            )?
            .l()?;
        let decor = env
            .call_method(
                window,
                jni_str!("getDecorView"),
                jni_sig!("()Landroid/view/View;"),
                &[],
            )?
            .l()?;
        let insets = env
            .call_method(
                decor,
                jni_str!("getRootWindowInsets"),
                jni_sig!("()Landroid/view/WindowInsets;"),
                &[],
            )?
            .l()?;
        if insets.is_null() {
            return Ok(None);
        }
        let sdk = env
            .get_static_field(
                jni_str!("android/os/Build$VERSION"),
                jni_str!("SDK_INT"),
                jni_sig!("I"),
            )?
            .i()?;
        if sdk >= 30 {
            let bars = env
                .call_static_method(
                    jni_str!("android/view/WindowInsets$Type"),
                    jni_str!("systemBars"),
                    jni_sig!("()I"),
                    &[],
                )?
                .i()?;
            let cutout = env
                .call_static_method(
                    jni_str!("android/view/WindowInsets$Type"),
                    jni_str!("displayCutout"),
                    jni_sig!("()I"),
                    &[],
                )?
                .i()?;
            let edges = env
                .call_method(
                    insets,
                    jni_str!("getInsets"),
                    jni_sig!("(I)Landroid/graphics/Insets;"),
                    &[JValue::Int(bars | cutout)],
                )?
                .l()?;
            Ok(Some(WindowInsets {
                top: env.get_field(&edges, jni_str!("top"), jni_sig!("I"))?.i()?,
                right: env
                    .get_field(&edges, jni_str!("right"), jni_sig!("I"))?
                    .i()?,
                bottom: env
                    .get_field(&edges, jni_str!("bottom"), jni_sig!("I"))?
                    .i()?,
                left: env
                    .get_field(&edges, jni_str!("left"), jni_sig!("I"))?
                    .i()?,
            }))
        } else {
            // API 26–29: стабильные отступы исключают высоту клавиатуры.
            Ok(Some(WindowInsets {
                top: env
                    .call_method(&insets, jni_str!("getStableInsetTop"), jni_sig!("()I"), &[])?
                    .i()?,
                right: env
                    .call_method(
                        &insets,
                        jni_str!("getStableInsetRight"),
                        jni_sig!("()I"),
                        &[],
                    )?
                    .i()?,
                bottom: env
                    .call_method(
                        &insets,
                        jni_str!("getStableInsetBottom"),
                        jni_sig!("()I"),
                        &[],
                    )?
                    .i()?,
                left: env
                    .call_method(
                        &insets,
                        jni_str!("getStableInsetLeft"),
                        jni_sig!("()I"),
                        &[],
                    )?
                    .i()?,
            }))
        }
    })
}
/// Открывает проверенную ссылку системным Android Intent.
pub fn open_url(url: &str) -> Result<()> {
    with_context(|env, activity| {
        let text = env.new_string(url)?;
        let uri = env
            .call_static_method(
                jni_str!("android/net/Uri"),
                jni_str!("parse"),
                jni_sig!("(Ljava/lang/String;)Landroid/net/Uri;"),
                &[JValue::Object(&text)],
            )?
            .l()?;
        let action = env.new_string("android.intent.action.VIEW")?;
        let intent = env.new_object(
            jni_str!("android/content/Intent"),
            jni_sig!("(Ljava/lang/String;Landroid/net/Uri;)V"),
            &[JValue::Object(&action), JValue::Object(&uri)],
        )?;
        env.call_method(
            &activity,
            jni_str!("startActivity"),
            jni_sig!("(Landroid/content/Intent;)V"),
            &[JValue::Object(&intent)],
        )?;
        Ok(())
    })
}

/// Находит приватный каталог Android с сохранением прежней истории.
pub fn data_dir() -> Result<PathBuf> {
    with_context(|env, activity| {
        let files = env
            .call_method(
                &activity,
                jni_str!("getFilesDir"),
                jni_sig!("()Ljava/io/File;"),
                &[],
            )?
            .l()?;
        let absolute = env
            .call_method(
                files,
                jni_str!("getAbsolutePath"),
                jni_sig!("()Ljava/lang/String;"),
                &[],
            )?
            .l()?;
        let files =
            PathBuf::from(java_string(env, absolute)?.context("Android не предоставил filesDir")?);
        // В прежних сборках private root мог лежать глубже filesDir.
        let mut histories = Vec::new();
        find_history(&files, 0, &mut histories)?;
        ensure!(
            histories.len() <= 1,
            "Найдено несколько историй. Автоматический выбор отключён, данные не изменены"
        );
        Ok(histories.pop().unwrap_or_else(|| files.join("Xopilot")))
    })
}

/// Ищет существующую историю в совместимых каталогах приложения.
fn find_history(dir: &Path, depth: usize, found: &mut Vec<PathBuf>) -> Result<()> {
    if dir.join("xopilot.db").is_file() {
        found.push(dir.to_owned());
        return Ok(());
    }
    if depth >= 6 {
        return Ok(());
    }
    for entry in std::fs::read_dir(dir)? {
        let entry = entry?;
        if entry.file_type()?.is_dir()
            && !["cache", "models", "materials"]
                .contains(&entry.file_name().to_string_lossy().as_ref())
        {
            find_history(&entry.path(), depth + 1, found)?;
        }
    }
    Ok(())
}

/// Получает прежний ключ Android Keystore; при утрате не подменяет историю новой.
pub fn database_key(existing: bool) -> Result<String> {
    with_context(|env, activity| {
        let prefs_name = env.new_string("xopilot_keys")?;
        let prefs = env
            .call_method(
                activity,
                jni_str!("getSharedPreferences"),
                jni_sig!("(Ljava/lang/String;I)Landroid/content/SharedPreferences;"),
                &[JValue::Object(&prefs_name), JValue::Int(0)],
            )?
            .l()?;
        let database_field = env.new_string("database")?;
        let iv_field = env.new_string("iv")?;
        let null = JObject::null();
        let wrapped = env
            .call_method(
                &prefs,
                jni_str!("getString"),
                jni_sig!("(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;"),
                &[JValue::Object(&database_field), JValue::Object(&null)],
            )?
            .l()?;
        let wrapped = java_string(env, wrapped)?;
        let iv = env
            .call_method(
                &prefs,
                jni_str!("getString"),
                jni_sig!("(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;"),
                &[JValue::Object(&iv_field), JValue::Object(&null)],
            )?
            .l()?;
        let iv = java_string(env, iv)?;
        ensure!(
            wrapped.is_some() == iv.is_some(),
            "Хранилище ключей повреждено"
        );
        ensure!(
            !existing || wrapped.is_some(),
            "Ключ существующей истории недоступен. Данные не изменены"
        );
        let provider = env.new_string("AndroidKeyStore")?;
        let store = env
            .call_static_method(
                jni_str!("java/security/KeyStore"),
                jni_str!("getInstance"),
                jni_sig!("(Ljava/lang/String;)Ljava/security/KeyStore;"),
                &[JValue::Object(&provider)],
            )?
            .l()?;
        env.call_method(
            &store,
            jni_str!("load"),
            jni_sig!("(Ljava/io/InputStream;[C)V"),
            &[JValue::Object(&null), JValue::Object(&null)],
        )?;
        let alias = env.new_string("xopilot.database.v1")?;
        let has_alias = env
            .call_method(
                &store,
                jni_str!("containsAlias"),
                jni_sig!("(Ljava/lang/String;)Z"),
                &[JValue::Object(&alias)],
            )?
            .z()?;
        ensure!(
            wrapped.is_none() || has_alias,
            "Android Keystore недоступен. Данные не изменены"
        );
        if !has_alias {
            let algorithm = env.new_string("AES")?;
            let generator = env
                .call_static_method(
                    jni_str!("javax/crypto/KeyGenerator"),
                    jni_str!("getInstance"),
                    jni_sig!("(Ljava/lang/String;Ljava/lang/String;)Ljavax/crypto/KeyGenerator;"),
                    &[JValue::Object(&algorithm), JValue::Object(&provider)],
                )?
                .l()?;
            let builder = env.new_object(
                jni_str!("android/security/keystore/KeyGenParameterSpec$Builder"),
                jni_sig!("(Ljava/lang/String;I)V"),
                &[JValue::Object(&alias), JValue::Int(3)],
            )?;
            env.call_method(
                &builder,
                jni_str!("setKeySize"),
                jni_sig!("(I)Landroid/security/keystore/KeyGenParameterSpec$Builder;"),
                &[JValue::Int(256)],
            )?;
            let gcm = env.new_string("GCM")?;
            let modes = env.new_object_array(1, jni_str!("java/lang/String"), &gcm)?;
            env.call_method(
                &builder,
                jni_str!("setBlockModes"),
                jni_sig!(
                    "([Ljava/lang/String;)Landroid/security/keystore/KeyGenParameterSpec$Builder;"
                ),
                &[JValue::Object(&modes)],
            )?;
            let padding = env.new_string("NoPadding")?;
            let paddings = env.new_object_array(1, jni_str!("java/lang/String"), &padding)?;
            env.call_method(
                &builder,
                jni_str!("setEncryptionPaddings"),
                jni_sig!(
                    "([Ljava/lang/String;)Landroid/security/keystore/KeyGenParameterSpec$Builder;"
                ),
                &[JValue::Object(&paddings)],
            )?;
            let spec = env
                .call_method(
                    builder,
                    jni_str!("build"),
                    jni_sig!("()Landroid/security/keystore/KeyGenParameterSpec;"),
                    &[],
                )?
                .l()?;
            env.call_method(
                &generator,
                jni_str!("init"),
                jni_sig!("(Ljava/security/spec/AlgorithmParameterSpec;)V"),
                &[JValue::Object(&spec)],
            )?;
            env.call_method(
                generator,
                jni_str!("generateKey"),
                jni_sig!("()Ljavax/crypto/SecretKey;"),
                &[],
            )?;
        }
        let key = env
            .call_method(
                store,
                jni_str!("getKey"),
                jni_sig!("(Ljava/lang/String;[C)Ljava/security/Key;"),
                &[JValue::Object(&alias), JValue::Object(&null)],
            )?
            .l()?;
        let transformation = env.new_string("AES/GCM/NoPadding")?;
        let cipher = env
            .call_static_method(
                jni_str!("javax/crypto/Cipher"),
                jni_str!("getInstance"),
                jni_sig!("(Ljava/lang/String;)Ljavax/crypto/Cipher;"),
                &[JValue::Object(&transformation)],
            )?
            .l()?;
        let mut secret;
        if let (Some(wrapped), Some(iv)) = (wrapped, iv) {
            let iv = env.byte_array_from_slice(&BASE64_STANDARD.decode(iv)?)?;
            let params = env.new_object(
                jni_str!("javax/crypto/spec/GCMParameterSpec"),
                jni_sig!("(I[B)V"),
                &[JValue::Int(128), JValue::Object(&iv)],
            )?;
            env.call_method(
                &cipher,
                jni_str!("init"),
                jni_sig!("(ILjava/security/Key;Ljava/security/spec/AlgorithmParameterSpec;)V"),
                &[
                    JValue::Int(2),
                    JValue::Object(&key),
                    JValue::Object(&params),
                ],
            )?;
            let bytes = env.byte_array_from_slice(&BASE64_STANDARD.decode(wrapped)?)?;
            let bytes = env
                .call_method(
                    &cipher,
                    jni_str!("doFinal"),
                    jni_sig!("([B)[B"),
                    &[JValue::Object(&bytes)],
                )?
                .l()?;
            secret = {
                let array = JByteArray::cast_local(env, bytes)?;
                env.convert_byte_array(array)?
            };
        } else {
            let random =
                env.new_object(jni_str!("java/security/SecureRandom"), jni_sig!("()V"), &[])?;
            let bytes = env.new_byte_array(32)?;
            env.call_method(
                random,
                jni_str!("nextBytes"),
                jni_sig!("([B)V"),
                &[JValue::Object(&bytes)],
            )?;
            secret = env.convert_byte_array(&bytes)?;
            env.call_method(
                &cipher,
                jni_str!("init"),
                jni_sig!("(ILjava/security/Key;)V"),
                &[JValue::Int(1), JValue::Object(&key)],
            )?;
            let encrypted = env
                .call_method(
                    &cipher,
                    jni_str!("doFinal"),
                    jni_sig!("([B)[B"),
                    &[JValue::Object(&bytes)],
                )?
                .l()?;
            let encrypted = {
                let array = JByteArray::cast_local(env, encrypted)?;
                env.convert_byte_array(array)?
            };
            let iv = env
                .call_method(cipher, jni_str!("getIV"), jni_sig!("()[B"), &[])?
                .l()?;
            let iv = {
                let array = JByteArray::cast_local(env, iv)?;
                env.convert_byte_array(array)?
            };
            let editor = env
                .call_method(
                    prefs,
                    jni_str!("edit"),
                    jni_sig!("()Landroid/content/SharedPreferences$Editor;"),
                    &[],
                )?
                .l()?;
            for (field, value) in [
                (&database_field, BASE64_STANDARD.encode(encrypted)),
                (&iv_field, BASE64_STANDARD.encode(iv)),
            ] {
                let value = env.new_string(value)?;
                env.call_method(&editor, jni_str!("putString"), jni_sig!("(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;"), &[JValue::Object(field), JValue::Object(&value)])?;
            }
            if !env
                .call_method(editor, jni_str!("commit"), jni_sig!("()Z"), &[])?
                .z()?
            {
                secret.fill(0);
                bail!("Не удалось сохранить ключ истории");
            }
        }
        ensure!(secret.len() == 32, "Некорректный ключ истории");
        let hex = hex::encode(&secret);
        secret.fill(0);
        Ok(hex)
    })
}
