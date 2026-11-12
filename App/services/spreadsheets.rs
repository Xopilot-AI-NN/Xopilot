// Описание: Чтение XLSX без запуска формул, макросов и внешних связей.
use anyhow::{Result, ensure};
use std::io::{Cursor, Read};

/// Ограничивает распаковку каждого XML независимо от размера сжатого архива.
fn xml(archive: &mut zip::ZipArchive<Cursor<&[u8]>>, name: &str) -> Result<String> {
    let mut file = archive.by_name(name)?;
    ensure!(file.size() <= 4 * 1024 * 1024, "Лист XLSX слишком большой");
    let mut text = String::new();
    file.by_ref()
        .take(4 * 1024 * 1024 + 1)
        .read_to_string(&mut text)?;
    ensure!(text.len() <= 4 * 1024 * 1024, "Превышен лимит XML");
    Ok(text)
}

/// Извлекает текстовые узлы, включая экранированные символы OOXML.
fn texts(source: &str, element: &[u8]) -> Result<Vec<String>> {
    use quick_xml::events::Event;
    let mut reader = quick_xml::Reader::from_str(source);
    let mut values = Vec::new();
    loop {
        match reader.read_event()? {
            Event::Start(tag) if tag.name().as_ref() == element => {
                let raw = reader.read_text(tag.name())?;
                values.push(quick_xml::escape::unescape(&raw)?.into_owned());
            }
            Event::Eof => break,
            _ => {}
        }
    }
    Ok(values)
}

/// Читает до десяти листов, сохраняя адреса ячеек и готовые значения формул.
/// Формулы не вычисляются. Отсутствующий кеш не заменяется выдуманным результатом.
pub fn read(raw: &[u8]) -> Result<String> {
    use quick_xml::events::Event;
    let mut archive = zip::ZipArchive::new(Cursor::new(raw))?;
    ensure!(archive.len() <= 4096, "Слишком много частей XLSX");
    // zip 9 декодирует имена с возможной ошибкой. Получаем принадлежащие нам строки
    // до чтения частей архива и сохраняем ошибку декодирования для пользователя.
    let files = archive
        .file_names()
        .map(|name| name.map(|name| name.into_owned()))
        .collect::<zip::result::ZipResult<Vec<_>>>()?;
    let shared = if files.iter().any(|name| name == "xl/sharedStrings.xml") {
        let source = xml(&mut archive, "xl/sharedStrings.xml")?;
        let mut strings = Vec::new();
        let mut reader = quick_xml::Reader::from_str(&source);
        loop {
            match reader.read_event()? {
                Event::Start(tag) if tag.name().as_ref() == b"si" => {
                    let content = reader.read_text(tag.name())?;
                    strings.push(texts(&content, b"t")?.join(""));
                }
                Event::Eof => break,
                _ => {}
            }
        }
        strings
    } else {
        Vec::new()
    };
    let mut names: Vec<_> = files
        .into_iter()
        .filter(|name| name.starts_with("xl/worksheets/") && name.ends_with(".xml"))
        .collect();
    names.sort();
    let mut output = String::new();
    for name in names.into_iter().take(10) {
        output.push_str(&format!("\n[{name}]\n"));
        let source = xml(&mut archive, &name)?;
        let mut reader = quick_xml::Reader::from_str(&source);
        loop {
            match reader.read_event()? {
                Event::Start(tag) if tag.name().as_ref() == b"c" => {
                    let mut address = String::new();
                    let mut kind = String::new();
                    for attribute in tag.attributes() {
                        let attribute = attribute?;
                        let value = attribute
                            .decode_and_unescape_value(reader.decoder())?
                            .into_owned();
                        match attribute.key.as_ref() {
                            b"r" => address = value,
                            b"t" => kind = value,
                            _ => {}
                        }
                    }
                    let inner = reader.read_text(tag.name())?;
                    let value = if kind == "inlineStr" {
                        texts(&inner, b"t")?.join("")
                    } else {
                        let value = texts(&inner, b"v")?.join("");
                        if kind == "s" {
                            let index: usize = value.parse()?;
                            shared
                                .get(index)
                                .cloned()
                                .ok_or_else(|| anyhow::anyhow!("Повреждён индекс строки XLSX"))?
                        } else {
                            value
                        }
                    };
                    output.push_str(&format!("{address}\t{value}\n"));
                    if output.chars().count() > super::attachments::MAX_TEXT_CHARS {
                        return Ok(super::attachments::truncate(
                            &output,
                            super::attachments::MAX_TEXT_CHARS,
                        ));
                    }
                }
                Event::Eof => break,
                _ => {}
            }
        }
    }
    Ok(output)
}
