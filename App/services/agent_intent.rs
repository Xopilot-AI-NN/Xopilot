// Описание: Проверка явно заданного текста перед созданием документа маленькой моделью.
use serde_json::Value;

/// Возвращает дословное содержимое текущей или продолженной просьбы, без догадок о названиях файлов.
pub fn canvas_content(
    history: &[Value],
    goal: &str,
) -> Option<String> {
    let lower = goal.to_lowercase();
    if ["пустой", "пустую", "empty"]
        .iter()
        .any(|word| lower.contains(word))
        || ![
            "canvas",
            "канвас",
            "канва",
            "то же",
            "тоже самое",
        ]
        .iter()
        .any(|word| lower.contains(word))
    {
        return None;
    }
    for message in history
        .iter()
        .rev()
        .filter(|message| message["role"] == "user")
        .take(4)
    {
        let Some(text) = message["content"].as_str() else {
            continue;
        };
        let lower = text.to_lowercase();
        for marker in
            ["с содержимым", "с текстом", "containing"]
        {
            let Some(start) = lower.find(marker) else {
                continue;
            };
            // Срез исходной строки считаем по символам: регистр Unicode может менять длину байтов.
            let offset = lower[..start].chars().count()
                + marker.chars().count();
            let rest = text
                .chars()
                .skip(offset)
                .collect::<String>();
            let rest =
                rest.trim().trim_start_matches(':').trim();
            for (open, close) in
                [('"', '"'), ('«', '»'), ('“', '”')]
            {
                if let Some(rest) = rest.strip_prefix(open)
                    && let Some(end) = rest.find(close)
                {
                    return Some(rest[..end].to_owned());
                }
            }
            // Новая просьба уже задала текст без кавычек: старую цитату не навязываем.
            return None;
        }
    }
    None
}

/// Подсчёт локальных Canvas требует чтения списка, ответ по памяти не является проверкой.
pub fn canvas_count_requested(text: &str) -> bool {
    let text = text.to_lowercase();
    let canvas =
        text.contains("canvas") || text.contains("канвас");
    let count = [
        "сколько",
        "how many",
        "count ",
        "посчитай",
        "количество",
    ]
    .iter()
    .any(|word| text.contains(word));
    let image = [
        "на фото",
        "на изображен",
        "на скриншот",
        "in the image",
        "in this image",
    ]
    .iter()
    .any(|word| text.contains(word));
    canvas && count && !image
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    /// Продолжение сохраняет пунктуацию цитаты; имя файла и явный пустой документ не подменяются.
    #[test]
    fn followup_preserves_explicit_content() {
        let history = vec![
            json!({"role":"user","content":"Создай файл с содержимым «Привет!» в ~/Desktop."}),
        ];
        assert_eq!(
            canvas_content(&history, "создай canvas")
                .as_deref(),
            Some("Привет!")
        );
        assert_eq!(
            canvas_content(&history, "тоже самое")
                .as_deref(),
            Some("Привет!")
        );
        assert_eq!(
            canvas_content(
                &history,
                "создай пустой canvas"
            ),
            None
        );
        assert_eq!(
            canvas_content(&history, "Привет"),
            None
        );
        let filename = vec![
            json!({"role":"user","content":"Создай файл «Привет!»"}),
        ];
        assert_eq!(
            canvas_content(&filename, "создай canvas"),
            None
        );
    }
}
