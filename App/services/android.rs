// Файл: App/services/android.rs
// Описание: Android Context и Keystore через JNI, без Flutter-моста.
// Alias и SharedPreferences совпадают с прежним приложением.
use anyhow::{Context, Result, bail, ensure};
use base64::{Engine, prelude::BASE64_STANDARD};
use jni::{
    JNIEnv, JavaVM,
    objects::{JByteArray, JObject, JString, JValue},
};
use std::path::{Path, PathBuf};

fn with_context<T>(call: impl FnOnce(&mut JNIEnv<'_>, JObject<'_>) -> Result<T>) -> Result<T> {
    let context = ndk_context::android_context();
    // VM и Activity принадлежат Dioxus/wry и живут до завершения Activity.
    let vm = unsafe { JavaVM::from_raw(context.vm().cast()) }?;
    let mut env = vm.attach_current_thread()?;
    let result = env.with_local_frame(96, |env| {
        let activity = unsafe { JObject::from_raw(context.context().cast()) };
        call(env, activity)
    });
    if env.exception_check().unwrap_or(false) {
        let _ = env.exception_clear();
    }
    result
}

fn java_string(env: &mut JNIEnv<'_>, object: JObject<'_>) -> Result<Option<String>> {
    if object.is_null() {
        return Ok(None);
    }
    Ok(Some(env.get_string(&JString::from(object))?.into()))
}

pub fn data_dir() -> Result<PathBuf> {
    with_context(|env, activity| {
        let files = env
            .call_method(&activity, "getFilesDir", "()Ljava/io/File;", &[])?
            .l()?;
        let absolute = env
            .call_method(files, "getAbsolutePath", "()Ljava/lang/String;", &[])?
            .l()?;
        let files =
            PathBuf::from(java_string(env, absolute)?.context("Android не предоставил filesDir")?);
        // В старых Flet-сборках private root мог лежать глубже filesDir.
        let mut histories = Vec::new();
        find_history(&files, 0, &mut histories)?;
        ensure!(
            histories.len() <= 1,
            "Найдено несколько историй. Автоматический выбор отключён, данные не изменены"
        );
        Ok(histories.pop().unwrap_or_else(|| files.join("Xopilot")))
    })
}

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

pub fn database_key(existing: bool) -> Result<String> {
    with_context(|env, activity| {
        let prefs_name = env.new_string("xopilot_keys")?;
        let prefs = env
            .call_method(
                activity,
                "getSharedPreferences",
                "(Ljava/lang/String;I)Landroid/content/SharedPreferences;",
                &[JValue::Object(&prefs_name), JValue::Int(0)],
            )?
            .l()?;
        let database_field = env.new_string("database")?;
        let iv_field = env.new_string("iv")?;
        let null = JObject::null();
        let wrapped = env
            .call_method(
                &prefs,
                "getString",
                "(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;",
                &[JValue::Object(&database_field), JValue::Object(&null)],
            )?
            .l()?;
        let wrapped = java_string(env, wrapped)?;
        let iv = env
            .call_method(
                &prefs,
                "getString",
                "(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;",
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
                "java/security/KeyStore",
                "getInstance",
                "(Ljava/lang/String;)Ljava/security/KeyStore;",
                &[JValue::Object(&provider)],
            )?
            .l()?;
        env.call_method(
            &store,
            "load",
            "(Ljava/io/InputStream;[C)V",
            &[JValue::Object(&null), JValue::Object(&null)],
        )?;
        let alias = env.new_string("xopilot.database.v1")?;
        let has_alias = env
            .call_method(
                &store,
                "containsAlias",
                "(Ljava/lang/String;)Z",
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
                    "javax/crypto/KeyGenerator",
                    "getInstance",
                    "(Ljava/lang/String;Ljava/lang/String;)Ljavax/crypto/KeyGenerator;",
                    &[JValue::Object(&algorithm), JValue::Object(&provider)],
                )?
                .l()?;
            let builder = env.new_object(
                "android/security/keystore/KeyGenParameterSpec$Builder",
                "(Ljava/lang/String;I)V",
                &[JValue::Object(&alias), JValue::Int(3)],
            )?;
            env.call_method(
                &builder,
                "setKeySize",
                "(I)Landroid/security/keystore/KeyGenParameterSpec$Builder;",
                &[JValue::Int(256)],
            )?;
            let gcm = env.new_string("GCM")?;
            let modes = env.new_object_array(1, "java/lang/String", &gcm)?;
            env.call_method(
                &builder,
                "setBlockModes",
                "([Ljava/lang/String;)Landroid/security/keystore/KeyGenParameterSpec$Builder;",
                &[JValue::Object(&modes)],
            )?;
            let padding = env.new_string("NoPadding")?;
            let paddings = env.new_object_array(1, "java/lang/String", &padding)?;
            env.call_method(
                &builder,
                "setEncryptionPaddings",
                "([Ljava/lang/String;)Landroid/security/keystore/KeyGenParameterSpec$Builder;",
                &[JValue::Object(&paddings)],
            )?;
            let spec = env
                .call_method(
                    builder,
                    "build",
                    "()Landroid/security/keystore/KeyGenParameterSpec;",
                    &[],
                )?
                .l()?;
            env.call_method(
                &generator,
                "init",
                "(Ljava/security/spec/AlgorithmParameterSpec;)V",
                &[JValue::Object(&spec)],
            )?;
            env.call_method(generator, "generateKey", "()Ljavax/crypto/SecretKey;", &[])?;
        }
        let key = env
            .call_method(
                store,
                "getKey",
                "(Ljava/lang/String;[C)Ljava/security/Key;",
                &[JValue::Object(&alias), JValue::Object(&null)],
            )?
            .l()?;
        let transformation = env.new_string("AES/GCM/NoPadding")?;
        let cipher = env
            .call_static_method(
                "javax/crypto/Cipher",
                "getInstance",
                "(Ljava/lang/String;)Ljavax/crypto/Cipher;",
                &[JValue::Object(&transformation)],
            )?
            .l()?;
        let mut secret;
        if let (Some(wrapped), Some(iv)) = (wrapped, iv) {
            let iv = env.byte_array_from_slice(&BASE64_STANDARD.decode(iv)?)?;
            let params = env.new_object(
                "javax/crypto/spec/GCMParameterSpec",
                "(I[B)V",
                &[JValue::Int(128), JValue::Object(&iv)],
            )?;
            env.call_method(
                &cipher,
                "init",
                "(ILjava/security/Key;Ljava/security/spec/AlgorithmParameterSpec;)V",
                &[
                    JValue::Int(2),
                    JValue::Object(&key),
                    JValue::Object(&params),
                ],
            )?;
            let bytes = env.byte_array_from_slice(&BASE64_STANDARD.decode(wrapped)?)?;
            let bytes = env
                .call_method(&cipher, "doFinal", "([B)[B", &[JValue::Object(&bytes)])?
                .l()?;
            secret = env.convert_byte_array(JByteArray::from(bytes))?;
        } else {
            let random = env.new_object("java/security/SecureRandom", "()V", &[])?;
            let bytes = env.new_byte_array(32)?;
            env.call_method(random, "nextBytes", "([B)V", &[JValue::Object(&bytes)])?;
            secret = env.convert_byte_array(&bytes)?;
            env.call_method(
                &cipher,
                "init",
                "(ILjava/security/Key;)V",
                &[JValue::Int(1), JValue::Object(&key)],
            )?;
            let encrypted = env
                .call_method(&cipher, "doFinal", "([B)[B", &[JValue::Object(&bytes)])?
                .l()?;
            let encrypted = env.convert_byte_array(JByteArray::from(encrypted))?;
            let iv = env.call_method(cipher, "getIV", "()[B", &[])?.l()?;
            let iv = env.convert_byte_array(JByteArray::from(iv))?;
            let editor = env
                .call_method(
                    prefs,
                    "edit",
                    "()Landroid/content/SharedPreferences$Editor;",
                    &[],
                )?
                .l()?;
            for (field, value) in [
                (&database_field, BASE64_STANDARD.encode(encrypted)),
                (&iv_field, BASE64_STANDARD.encode(iv)),
            ] {
                let value = env.new_string(value)?;
                env.call_method(&editor, "putString", "(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;", &[JValue::Object(field), JValue::Object(&value)])?;
            }
            if !env.call_method(editor, "commit", "()Z", &[])?.z()? {
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
