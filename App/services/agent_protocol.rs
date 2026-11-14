// Описание: Отделяем разговорный ответ от протокола, даже если модель добавила пояснение.
use super::agent::{Call, Reply};
use anyhow::{Context, Result, bail, ensure};
use serde_json::Value;

/// Замечает заявления об изменениях: без успешного инструмента их нельзя выдавать за результат.
pub fn claims_change(text: &str) -> bool {
    let text = text.to_lowercase();
    let first = text
        .split_whitespace()
        .next()
        .unwrap_or("")
        .trim_matches(['.', ',', ':', '!']);
    if [
        "создан",
        "создана",
        "создано",
        "созданы",
        "сохранён",
        "сохранен",
        "сохранена",
        "сохранено",
        "сохранены",
        "обновлён",
        "удалён",
    ]
    .contains(&first)
    {
        return true;
    }
    [
        "создаю",
        "создал",
        "успешно создан",
        "был создан",
        "была создана",
        "сохранил",
        "успешно сохран",
        "записал",
        "обновил",
        "удалил",
        "i created",
        "i have created",
        "i saved",
        "successfully created",
        "has been created",
        "i updated",
        "i deleted",
    ]
    .iter()
    .any(|phrase| {
        text.match_indices(phrase).any(|(offset, _)| {
            let before = &text[..offset];
            !before.ends_with("не ")
                && !before.ends_with("not ")
        })
    })
}

/// Находит только полные объекты управляющего протокола и не исполняет обрывки JSON.
fn embedded(text: &str) -> Result<Vec<Value>> {
    let mut values = Vec::new();
    let mut offset = 0;
    while let Some(relative) = text[offset..].find('{') {
        let start = offset + relative;
        let mut stream =
            serde_json::Deserializer::from_str(
                &text[start..],
            )
            .into_iter::<Value>();
        match stream.next() {
            Some(Ok(value)) => {
                offset = start + stream.byte_offset();
                if is_protocol(&value) {
                    values.push(value);
                    ensure!(
                        values.len() <= 4,
                        "Слишком много действий в ответе"
                    );
                }
            }
            _ => {
                let fragment = &text[start..];
                if [
                    "\"tool\"",
                    "\"tool_name\"",
                    "\"actions\"",
                    "\"final\"",
                ]
                .iter()
                .any(|key| fragment.contains(key))
                {
                    bail!(
                        "Незавершённое действие: нужен целый JSON"
                    );
                }
                offset = start + 1;
            }
        }
    }
    Ok(values)
}
/// Узнаёт формат управления, не принимая произвольные JSON-данные пользователя за команду.
fn is_protocol(value: &Value) -> bool {
    ["tool", "tool_name", "actions", "final"]
        .iter()
        .any(|key| value.get(key).is_some())
}
/// Убирает внешний маркер final, но не скрывает ошибочно вложенную команду.
fn clean_final(
    text: &str,
    bare_marker: bool,
) -> Result<String> {
    let text = text.trim();
    let prefixed = text.get(..6).is_some_and(|prefix| {
        prefix.eq_ignore_ascii_case("final:")
            || (bare_marker
                && prefix.eq_ignore_ascii_case("final "))
    });
    let mut text =
        if prefixed { text[6..].trim() } else { text };
    if prefixed && text.starts_with("[]") {
        text = text[2..].trim();
    }
    ensure!(!text.is_empty(), "Финальный ответ пуст");
    ensure!(
        embedded(text)?.is_empty(),
        "В final попало действие: верни его отдельным tool/arguments, затем дай обычный ответ"
    );
    Ok(text.into())
}
/// Разбирает ответы с пояснением перед JSON; смешанный или оборванный пакет отклоняется целиком.
pub fn parse(text: &str) -> Result<Reply> {
    let text = text.trim();
    let text = text
        .strip_prefix("```json")
        .or_else(|| text.strip_prefix("```xopilot"))
        .or_else(|| text.strip_prefix("```"))
        .and_then(|s| s.trim().strip_suffix("```"))
        .unwrap_or(text)
        .trim();
    let values = if text.starts_with('{') {
        serde_json::Deserializer::from_str(text)
            .into_iter::<Value>()
            .take(5)
            .collect::<std::result::Result<Vec<_>, _>>()
            .context(
                "Модель вернула незавершённое действие",
            )?
    } else {
        embedded(text)?
    };
    if values.is_empty() {
        return Ok(Reply::Final(clean_final(text, true)?));
    }
    ensure!(
        values.len() <= 4,
        "В ответе слишком много объектов"
    );
    if values.len() == 1 && values[0].get("final").is_some()
    {
        ensure!(
            values[0].get("tool").is_none()
                && values[0].get("tool_name").is_none()
                && values[0].get("actions").is_none(),
            "Нельзя смешивать ответ с действием"
        );
        return Ok(Reply::Final(clean_final(
            values[0]["final"].as_str().context(
                "final должен быть обычным текстом",
            )?,
            false,
        )?));
    }
    let mut calls = Vec::new();
    for value in values {
        ensure!(
            value.get("final").is_none(),
            "Нельзя смешивать final с действиями"
        );
        if let Some(actions) = value.get("actions") {
            let packet: Vec<Call> =
                serde_json::from_value(actions.clone())?;
            ensure!(
                !packet.is_empty(),
                "Пакет действий пуст"
            );
            calls.extend(packet);
        } else {
            calls.push(serde_json::from_value::<Call>(
                value,
            )?);
        }
    }
    ensure!(
        !calls.is_empty() && calls.len() <= 4,
        "В пакете должно быть от 1 до 4 действий"
    );
    Ok(Reply::Calls(calls))
}
#[cfg(test)]
mod tests {
    /// Gemma использует tool_name: вызов остаётся тем же Call и проходит обычные разрешения.
    #[test]
    fn native_tool_name_is_normalized_without_ambiguous_commands()
     {
        let parsed=super::parse("Использую инструмент. {\"tool_name\":\"list_canvases\",\"arguments\":{}}").unwrap();
        assert!(
            matches!(parsed,super::Reply::Calls(calls) if calls.len()==1 && calls[0].tool=="list_canvases")
        );
        assert!(super::parse("{\"tool\":\"read_canvas\",\"tool_name\":\"write_project_file\",\"arguments\":{}}").is_err());
        assert!(super::parse("{\"final\":\"Готово\",\"tool_name\":\"list_canvases\"}").is_err());
        assert!(
            super::parse("Ответ. {\"tool_name\":").is_err()
        );
    }

    /// Отличает обещание выполнить действие от описания отсутствующих документов.
    #[test]
    fn change_claim_requires_receipt() {
        assert!(super::claims_change(
            "Создаю Canvas с названием «Привет!»"
        ));
        assert!(super::claims_change("Я создал документ."));
        assert!(super::claims_change(
            "Создан новый канвас."
        ));
        assert!(!super::claims_change(
            "У вас пока нет созданных канвасов."
        ));
        assert!(!super::claims_change(
            "Какое содержимое добавить?"
        ));
        assert!(!super::claims_change(
            "Я не создал документ."
        ));
        assert!(!super::claims_change(
            "Создание документа доступно через Canvas."
        ));
    }
    /// Пояснение перед командой не превращает команду в показанный пользователю текст.
    #[test]
    fn prose_and_final_markers_do_not_leak_protocol() {
        assert!(matches!(
            super::parse(
                "Для проверки использую инструмент.\n{\"tool\":\"list_canvases\",\"arguments\":{}}"
            )
            .unwrap(),
            super::Reply::Calls(_)
        ));
        assert!(
            matches!(super::parse("final: [] Канвасов пока нет.").unwrap(),super::Reply::Final(text) if text=="Канвасов пока нет.")
        );
        assert!(matches!(
            super::parse(
                "final: {\"tool\":\"read_canvas\",\"arguments\":{\"id\":\"abc\"}} Я проверил"
            )
            .unwrap(),
            super::Reply::Calls(_)
        ));
        assert!(
            super::parse(
                "{\"final\":\"{\\\"tool\\\":\\\"read_canvas\\\",\\\"arguments\\\":{}} Готово\"}"
            )
            .is_err()
        );
        assert!(
            super::parse("Сделаю. {\"tool\":\"list_canvases\",\"arguments\":{}} {\"tool\":")
                .is_err()
        );
    }
}
