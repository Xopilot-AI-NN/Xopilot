// Системный Android TTS через JNI. Выбираю только установленный голос без сети.
use super::android::with_context;
use anyhow::{Context, Result, ensure};
use jni::{
    jni_sig, jni_str,
    objects::{JObject, JValue},
    refs::Global,
};
use std::time::{Duration, Instant};
use tokio_util::sync::CancellationToken;

struct Engine(Global<JObject<'static>>);
impl Drop for Engine {
    /// Освобождаю системную очередь даже при ошибке и отмене.
    fn drop(&mut self) {
        let _ = with_context(|env, _| {
            env.call_method(
                &*self.0,
                jni_str!("stop"),
                jni_sig!("()I"),
                &[],
            )?;
            env.call_method(
                &*self.0,
                jni_str!("shutdown"),
                jni_sig!("()V"),
                &[],
            )?;
            Ok(())
        });
    }
}

/// Инициализация и ожидание идут в worker, Activity и UI не блокируются.
pub(super) fn speak(
    parts: Vec<String>,
    stop: CancellationToken,
) -> Result<()> {
    let engine = with_context(|env, activity| {
        let context = env
            .call_method(
                &activity,
                jni_str!("getApplicationContext"),
                jni_sig!("()Landroid/content/Context;"),
                &[],
            )?
            .l()?;
        let object=env.new_object(jni_str!("android/speech/tts/TextToSpeech"),jni_sig!("(Landroid/content/Context;Landroid/speech/tts/TextToSpeech$OnInitListener;)V"),&[JValue::Object(&context),JValue::Object(&JObject::null())])?;
        Ok(Engine(env.new_global_ref(object)?))
    })?;
    super::speech::report(
        "Подготовка системного голоса",
        0,
        None,
    );
    let began = Instant::now();
    loop {
        ensure!(
            !stop.is_cancelled(),
            "Озвучивание остановлено"
        );
        let available = with_context(|env, _| {
            let language = env.new_string("ru")?;
            let locale = env.new_object(
                jni_str!("java/util/Locale"),
                jni_sig!("(Ljava/lang/String;)V"),
                &[JValue::Object(&language)],
            )?;
            Ok(env
                .call_method(
                    &*engine.0,
                    jni_str!("setLanguage"),
                    jni_sig!("(Ljava/util/Locale;)I"),
                    &[JValue::Object(&locale)],
                )?
                .i()?
                >= 0)
        })?;
        if available {
            break;
        }
        ensure!(
            began.elapsed() < Duration::from_secs(8),
            "Русский системный голос недоступен на устройстве"
        );
        std::thread::sleep(Duration::from_millis(100));
    }
    // Исключаю голоса, требующие сети или ещё не установленного пакета данных.
    with_context(|env, _| {
        let voices = env
            .call_method(
                &*engine.0,
                jni_str!("getVoices"),
                jni_sig!("()Ljava/util/Set;"),
                &[],
            )?
            .l()?;
        ensure!(
            !voices.is_null(),
            "Android не вернул список голосов"
        );
        let iterator = env
            .call_method(
                &voices,
                jni_str!("iterator"),
                jni_sig!("()Ljava/util/Iterator;"),
                &[],
            )?
            .l()?;
        let mut selected = None;
        while env
            .call_method(
                &iterator,
                jni_str!("hasNext"),
                jni_sig!("()Z"),
                &[],
            )?
            .z()?
        {
            let candidate=env.with_local_frame(24, |env| -> Result<Option<Global<JObject<'static>>>> {
                let voice=env.call_method(&iterator,jni_str!("next"),jni_sig!("()Ljava/lang/Object;"),&[])?.l()?;
                let network=env.call_method(&voice,jni_str!("isNetworkConnectionRequired"),jni_sig!("()Z"),&[])?.z()?;
                let locale=env.call_method(&voice,jni_str!("getLocale"),jni_sig!("()Ljava/util/Locale;"),&[])?.l()?;
                let value=env.call_method(&locale,jni_str!("getLanguage"),jni_sig!("()Ljava/lang/String;"),&[])?.l()?;
                let language=jni::objects::JString::cast_local(env,value)?;
                let language=language.try_to_string(env)?;
                let features=env.call_method(&voice,jni_str!("getFeatures"),jni_sig!("()Ljava/util/Set;"),&[])?.l()?;
                let marker=env.new_string("notInstalled")?;
                let missing=!features.is_null() && env.call_method(&features,jni_str!("contains"),jni_sig!("(Ljava/lang/Object;)Z"),&[JValue::Object(&marker)])?.z()?;
                if !network && !missing && language=="ru" {Ok(Some(env.new_global_ref(voice)?))}else{Ok(None)}
            })?;
            if candidate.is_some() {
                selected = candidate;
                break;
            }
        }
        let voice=selected.context("Установленный локальный русский голос не найден")?;
        ensure!(
            env.call_method(
                &*engine.0,
                jni_str!("setVoice"),
                jni_sig!("(Landroid/speech/tts/Voice;)I"),
                &[JValue::Object(&voice)]
            )?
            .i()?
                == 0,
            "Не удалось выбрать русский голос"
        );
        Ok(())
    })?;
    for (index, text) in parts.into_iter().enumerate() {
        ensure!(
            !stop.is_cancelled(),
            "Озвучивание остановлено"
        );
        super::speech::report("Озвучивание", 0, None);
        with_context(|env, _| {
            let text = env.new_string(text)?;
            let id =
                env.new_string(format!("xopilot-{index}"))?;
            let status=env.call_method(&*engine.0,jni_str!("speak"),jni_sig!("(Ljava/lang/CharSequence;ILandroid/os/Bundle;Ljava/lang/String;)I"),&[JValue::Object(&text),JValue::Int(0),JValue::Object(&JObject::null()),JValue::Object(&id)])?.i()?;
            ensure!(
                status == 0,
                "Android не принял текст для озвучивания"
            );
            Ok(())
        })?;
        let began = Instant::now();
        let mut started = false;
        loop {
            ensure!(
                !stop.is_cancelled(),
                "Озвучивание остановлено"
            );
            let playing = with_context(|env, _| {
                Ok(env
                    .call_method(
                        &*engine.0,
                        jni_str!("isSpeaking"),
                        jni_sig!("()Z"),
                        &[],
                    )?
                    .z()?)
            })?;
            if playing {
                started = true;
            } else if started {
                break;
            }
            ensure!(
                began.elapsed()
                    < Duration::from_secs(if started {
                        60
                    } else {
                        8
                    }),
                "Системный голос не ответил"
            );
            std::thread::sleep(Duration::from_millis(25));
        }
    }
    super::speech::report("", 0, None);
    Ok(())
}
