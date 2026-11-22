// Публикация PNG в общих «Загрузках» Android 10+ через MediaStore.
use super::android::with_context;
use anyhow::{Result, ensure};
use jni::{
    Env, jni_sig, jni_str,
    objects::{JObject, JValue},
};

/// На Android 9 и старше вызывающий код использует каталог приложения.
pub(super) fn publish_png(
    name: &str,
    bytes: &[u8],
) -> Result<bool> {
    with_context(|env, activity| {
        let sdk = env
            .get_static_field(
                jni_str!("android/os/Build$VERSION"),
                jni_str!("SDK_INT"),
                jni_sig!("I"),
            )?
            .i()?;
        if sdk < 29 {
            return Ok(false);
        }
        let resolver = env
            .call_method(
                activity,
                jni_str!("getContentResolver"),
                jni_sig!(
                    "()Landroid/content/ContentResolver;"
                ),
                &[],
            )?
            .l()?;
        let downloads = env
            .get_static_field(
                jni_str!(
                    "android/provider/MediaStore$Downloads"
                ),
                jni_str!("EXTERNAL_CONTENT_URI"),
                jni_sig!("Landroid/net/Uri;"),
            )?
            .l()?;
        let values = env.new_object(
            jni_str!("android/content/ContentValues"),
            jni_sig!("()V"),
            &[],
        )?;
        for (key, value) in [
            ("_display_name", name),
            ("mime_type", "image/png"),
            ("relative_path", "Download/Xopilot"),
        ] {
            let key = env.new_string(key)?;
            let value = env.new_string(value)?;
            env.call_method(
                &values,
                jni_str!("put"),
                jni_sig!("(Ljava/lang/String;Ljava/lang/String;)V"),
                &[JValue::Object(&key), JValue::Object(&value)],
            )?;
        }
        set_pending(env, &values, 1)?;
        let uri = env.call_method(
            &resolver,
            jni_str!("insert"),
            jni_sig!("(Landroid/net/Uri;Landroid/content/ContentValues;)Landroid/net/Uri;"),
            &[JValue::Object(&downloads), JValue::Object(&values)],
        )?.l()?;
        ensure!(
            !uri.is_null(),
            "Android не создал файл в Загрузках"
        );

        // Медиа становится видимым после записи. При ошибке удаляем незавершённую запись.
        let result = (|| -> Result<()> {
            let data = env.byte_array_from_slice(bytes)?;
            let stream = env.call_method(
                &resolver,
                jni_str!("openOutputStream"),
                jni_sig!("(Landroid/net/Uri;)Ljava/io/OutputStream;"),
                &[JValue::Object(&uri)],
            )?.l()?;
            ensure!(
                !stream.is_null(),
                "Android не открыл файл для записи"
            );
            let write = env.call_method(
                &stream,
                jni_str!("write"),
                jni_sig!("([B)V"),
                &[JValue::Object(&data)],
            );
            if write.is_err() && env.exception_check() {
                env.exception_clear();
            }
            let close = env.call_method(
                &stream,
                jni_str!("close"),
                jni_sig!("()V"),
                &[],
            );
            write?;
            close?;
            env.call_method(
                &values,
                jni_str!("clear"),
                jni_sig!("()V"),
                &[],
            )?;
            set_pending(env, &values, 0)?;
            let updated = env.call_method(
                &resolver,
                jni_str!("update"),
                jni_sig!("(Landroid/net/Uri;Landroid/content/ContentValues;Ljava/lang/String;[Ljava/lang/String;)I"),
                &[
                    JValue::Object(&uri),
                    JValue::Object(&values),
                    JValue::Object(&JObject::null()),
                    JValue::Object(&JObject::null()),
                ],
            )?.i()?;
            ensure!(
                updated == 1,
                "Android не опубликовал PNG"
            );
            Ok(())
        })();
        if result.is_err() {
            if env.exception_check() {
                env.exception_clear();
            }
            let _ = env.call_method(
                &resolver,
                jni_str!("delete"),
                jni_sig!("(Landroid/net/Uri;Ljava/lang/String;[Ljava/lang/String;)I"),
                &[
                    JValue::Object(&uri),
                    JValue::Object(&JObject::null()),
                    JValue::Object(&JObject::null()),
                ],
            );
        }
        result?;
        Ok(true)
    })
}

/// ContentValues принимает boxed Integer для флага IS_PENDING.
fn set_pending(
    env: &mut Env<'_>,
    values: &JObject<'_>,
    pending: i32,
) -> Result<()> {
    let key = env.new_string("is_pending")?;
    let value = env
        .call_static_method(
            jni_str!("java/lang/Integer"),
            jni_str!("valueOf"),
            jni_sig!("(I)Ljava/lang/Integer;"),
            &[JValue::Int(pending)],
        )?
        .l()?;
    env.call_method(
        values,
        jni_str!("put"),
        jni_sig!(
            "(Ljava/lang/String;Ljava/lang/Integer;)V"
        ),
        &[JValue::Object(&key), JValue::Object(&value)],
    )?;
    Ok(())
}
