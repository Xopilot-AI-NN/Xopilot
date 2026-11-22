// Добавил общий контроль озвучивания: новая речь отменяет прежнюю, остановка закрывает вывод.
use anyhow::{Result, ensure};
use std::sync::{Mutex, OnceLock};
use tokio_util::sync::CancellationToken;

#[derive(Clone, Default, PartialEq)]
pub struct Status {
    pub phase: String,
    pub downloaded: u64,
    pub total: Option<u64>,
}
static CURRENT: OnceLock<
    Mutex<Option<(CancellationToken, bool)>>,
> = OnceLock::new();
static STATUS: OnceLock<Mutex<Status>> = OnceLock::new();
static PLAYBACK: OnceLock<tokio::sync::Mutex<()>> =
    OnceLock::new();
struct SpeechLifetime;
impl Drop for SpeechLifetime {
    /// Прогресс исчезает при успехе, ошибке и отмене текущего проигрывания.
    fn drop(&mut self) {
        report("", 0, None);
    }
}

/// Новый запрос не воспроизводится одновременно с предыдущим.
pub fn begin() -> CancellationToken {
    begin_kind(false)
}
/// Отдельная загрузка продолжает работу при сворачивании окна.
pub fn begin_download() -> CancellationToken {
    begin_kind(true)
}
fn begin_kind(background: bool) -> CancellationToken {
    stop();
    let token = CancellationToken::new();
    *CURRENT
        .get_or_init(Default::default)
        .lock()
        .unwrap() = Some((token.clone(), background));
    token
}
/// Использую один токен для подготовки движка, синтеза и воспроизведения.
pub fn stop() {
    if let Some((token, _)) = CURRENT
        .get_or_init(Default::default)
        .lock()
        .unwrap()
        .take()
    {
        token.cancel();
    }
    report("", 0, None);
}
/// Скрытое окно останавливает звук, но не отдельную загрузку выбранного голоса.
pub fn stop_hidden() {
    let mut current = CURRENT
        .get_or_init(Default::default)
        .lock()
        .unwrap();
    if current
        .as_ref()
        .is_some_and(|(_, background)| !*background)
    {
        if let Some((token, _)) = current.take() {
            token.cancel();
        }
        report("", 0, None);
    }
}
/// Возвращаю состояние подготовки голоса для интерфейса.
pub fn status() -> Status {
    STATUS
        .get_or_init(Default::default)
        .lock()
        .unwrap()
        .clone()
}
/// Показываю только фактический этап, без выдуманного процента готовности.
pub(super) fn report(
    phase: &str,
    downloaded: u64,
    total: Option<u64>,
) {
    *STATUS.get_or_init(Default::default).lock().unwrap() =
        Status {
            phase: phase.into(),
            downloaded,
            total,
        };
}

/// Убираю разметку и блоки кода, затем делю длинный ответ без разрыва UTF-8.
pub fn chunks(text: &str) -> Vec<String> {
    use pulldown_cmark::{Event, Parser, Tag, TagEnd};
    let mut code = false;
    let mut plain = String::new();
    for event in Parser::new(text) {
        match event {
            Event::Start(Tag::CodeBlock(_)) => code = true,
            Event::End(TagEnd::CodeBlock) => code = false,
            Event::Text(text) | Event::Code(text)
                if !code =>
            {
                plain.push_str(&text);
                plain.push(' ');
            }
            Event::SoftBreak | Event::HardBreak => {
                plain.push(' ')
            }
            _ => {}
        }
    }
    let mut result = Vec::new();
    let mut chunk = String::new();
    for word in plain.split_whitespace() {
        if chunk.chars().count() + word.chars().count()
            > 300
            && !chunk.is_empty()
        {
            result.push(std::mem::take(&mut chunk));
        }
        if !chunk.is_empty() {
            chunk.push(' ')
        }
        chunk.push_str(word);
        if chunk.chars().count() >= 300 {
            result.push(std::mem::take(&mut chunk));
        }
    }
    if !chunk.is_empty() {
        result.push(chunk)
    }
    result
}

/// Озвучиваю ответ на выбранной платформе. Переписка не передаётся голосовому облаку.
pub async fn speak(
    text: String,
    token: CancellationToken,
) -> Result<()> {
    let _playback = tokio::select! {_=token.cancelled()=>anyhow::bail!("Озвучивание остановлено"),guard=PLAYBACK.get_or_init(Default::default).lock()=>guard};
    let _status = SpeechLifetime;
    report("Подготовка голоса", 0, None);
    ensure!(
        text.chars().count() <= 12000,
        "Ответ длиннее 12000 символов, озвучивание ограничено"
    );
    let parts = chunks(&text);
    ensure!(
        !parts.is_empty(),
        "Нет текста для озвучивания"
    );
    #[cfg(all(target_os = "linux", feature = "desktop"))]
    {
        for part in parts {
            ensure!(
                !token.is_cancelled(),
                "Озвучивание остановлено"
            );
            let work = token.clone();
            let audio = super::runtime::background(
                super::speech_piper::synthesize(part, work),
            )
            .await?;
            report("Озвучивание", 0, None);
            let work = token.clone();
            super::runtime::blocking(move || {
                super::voice_native::play(
                    audio, 22050, work,
                )
            })
            .await?;
        }
        report("", 0, None);
        Ok(())
    }
    #[cfg(target_os = "android")]
    {
        super::runtime::blocking(move || {
            super::speech_android::speak(parts, token)
        })
        .await
    }
    #[cfg(not(any(
        target_os = "android",
        all(target_os = "linux", feature = "desktop")
    )))]
    {
        let encoded = serde_json::to_string(&parts)?;
        let script = include_str!("speech_play.js")
            .replace("__XOPILOT_TEXT__", &encoded);
        let mut bridge = dioxus::document::eval(&script);
        tokio::select! {
            result=bridge.recv::<serde_json::Value>()=>{
                let result=result?;
                ensure!(result["ok"]==true,"{}",result["error"].as_str().unwrap_or("Ошибка голоса"));
                report("",0,None);
                Ok(())
            },
            _=token.cancelled()=>{let _=bridge.send("stop");anyhow::bail!("Озвучивание остановлено")}
        }
    }
}

/// Дополнительный голос выбирается отдельной кнопкой с указанием условий его использования.
pub async fn install_piper(
    token: CancellationToken,
) -> Result<()> {
    #[cfg(all(target_os = "linux", feature = "desktop"))]
    {
        super::runtime::background(async move {
            let _playback=tokio::select!{_=token.cancelled()=>anyhow::bail!("Загрузка голоса остановлена"),guard=PLAYBACK.get_or_init(Default::default).lock()=>guard};
            let _status=SpeechLifetime;
            super::speech_piper::enable(token).await
        }).await
    }
    #[cfg(not(all(
        target_os = "linux",
        feature = "desktop"
    )))]
    {
        let _ = token;
        anyhow::bail!(
            "Piper загружается в Linux-версии; на этом устройстве используется системный голос"
        )
    }
}
/// На Linux возвращаю базовый русский голос без удаления загруженной модели.
pub fn use_system_voice() -> Result<()> {
    stop();
    #[cfg(all(target_os = "linux", feature = "desktop"))]
    {
        super::speech_piper::disable()
    }
    #[cfg(not(all(
        target_os = "linux",
        feature = "desktop"
    )))]
    {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    /// Не зачитываю пользователю программный код и управляющую разметку.
    #[test]
    fn speaks_text_without_code_blocks() {
        let result=chunks("**Привет**, мир!\n```rust\nsecret();\n```\nКонец.").join(" ");
        assert!(result.contains("Привет"));
        assert!(!result.contains("secret"));
        assert!(result.contains("Конец"));
    }
    /// Длинный русский текст не режется по байтам и не теряет слова.
    #[test]
    fn chunks_preserve_unicode() {
        let text = "Проверка ".repeat(200);
        let parts = chunks(&text);
        assert!(parts.len() > 1);
        assert!(
            parts.iter().all(|p| p.chars().count() <= 310)
        );
        assert_eq!(parts.join(" "), text.trim());
    }
}
