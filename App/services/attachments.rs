// Файл: App/services/attachments.rs
// Разработчик: DenBroLiik
// Описание: Чтение изображений, текста, PDF и DOCX в Rust.
use anyhow::{Context, Result, bail, ensure};
use image::{ImageReader, codecs::jpeg::JpegEncoder};
use std::{
    io::{Cursor, Read},
    path::Path,
};

pub const MAX_TEXT_CHARS: usize = 20_000;
pub const MAX_FILE_BYTES: u64 = 32 * 1024 * 1024;
pub const MAX_IMAGE_SIDE: u32 = 1024;

#[derive(Default, Debug)]
pub struct AttachmentParts {
    pub text_notes: Vec<String>,
    pub images: Vec<Vec<u8>>,
}

pub fn truncate(text: &str, limit: usize) -> String {
    let mut chars = text.chars();
    let mut value: String = chars.by_ref().take(limit).collect();
    if chars.next().is_some() {
        value.push_str("\n…[обрезано]");
    }
    value
}

pub fn downscale_image_bytes(raw: &[u8]) -> Result<Vec<u8>> {
    let mut reader = ImageReader::new(Cursor::new(raw)).with_guessed_format()?;
    let mut limits = image::Limits::default();
    limits.max_image_width = Some(16_384);
    limits.max_image_height = Some(16_384);
    limits.max_alloc = Some(128 * 1024 * 1024);
    reader.limits(limits);
    let image = reader
        .decode()?
        .thumbnail(MAX_IMAGE_SIDE, MAX_IMAGE_SIDE)
        .to_rgb8();
    let mut bytes = Vec::new();
    JpegEncoder::new_with_quality(&mut bytes, 87).encode_image(&image)?;
    Ok(bytes)
}

fn read_docx(raw: &[u8]) -> Result<String> {
    let mut archive = zip::ZipArchive::new(Cursor::new(raw))?;
    let mut document = archive.by_name("word/document.xml")?;
    ensure!(
        document.size() <= 4 * 1024 * 1024,
        "DOCX содержит слишком много текста"
    );
    let mut xml = String::new();
    document
        .by_ref()
        .take(4 * 1024 * 1024 + 1)
        .read_to_string(&mut xml)?;
    ensure!(
        xml.len() <= 4 * 1024 * 1024,
        "DOCX превышает лимит распаковки"
    );
    let mut reader = quick_xml::Reader::from_str(&xml);
    let mut text = String::new();
    let mut in_text = false;
    loop {
        use quick_xml::events::Event;
        match reader.read_event()? {
            Event::Start(tag) if tag.name().as_ref() == b"w:t" => in_text = true,
            Event::End(tag) if tag.name().as_ref() == b"w:t" => in_text = false,
            Event::End(tag) if tag.name().as_ref() == b"w:p" => text.push('\n'),
            Event::Text(value) if in_text => text.push_str(&value.xml_content()?),
            Event::GeneralRef(value) if in_text => {
                let name = value.decode()?;
                text.push_str(&quick_xml::escape::unescape(&format!("&{name};"))?);
            }
            Event::Eof => break,
            _ => {}
        }
        if text.len() > MAX_TEXT_CHARS * 4 {
            break;
        }
    }
    Ok(truncate(text.trim(), MAX_TEXT_CHARS))
}

fn read_attachment(path: &Path) -> Result<AttachmentParts> {
    ensure!(path.is_file(), "Файл недоступен на диске");
    ensure!(
        path.metadata()?.len() <= MAX_FILE_BYTES,
        "Размер вложения превышает 32 МиБ"
    );
    let mut raw = Vec::new();
    std::fs::File::open(path)?
        .take(MAX_FILE_BYTES + 1)
        .read_to_end(&mut raw)?;
    ensure!(
        raw.len() as u64 <= MAX_FILE_BYTES,
        "Файл увеличился сверх лимита"
    );
    let ext = path
        .extension()
        .unwrap_or_default()
        .to_string_lossy()
        .to_lowercase();
    let mut result = AttachmentParts::default();
    if ["jpg", "jpeg", "png", "webp", "bmp", "gif"].contains(&ext.as_str()) {
        result.images.push(downscale_image_bytes(&raw)?);
        return Ok(result);
    }
    let text = match ext.as_str() {
        "pdf" => truncate(
            &pdf_extract::extract_text_from_mem(&raw).context("Не удалось прочитать PDF")?,
            MAX_TEXT_CHARS,
        ),
        "docx" => read_docx(&raw)?,
        "mp4" | "mov" | "avi" | "mkv" | "webm" => {
            bail!("Прикрепите кадры видео как изображения: извлечение видео ещё не перенесено")
        }
        _ => {
            ensure!(
                !raw.iter().take(8192).any(|b| *b == 0),
                "Двоичный формат не поддерживается для анализа"
            );
            truncate(
                &String::from_utf8_lossy(&raw[..raw.len().min(MAX_TEXT_CHARS * 4)]),
                MAX_TEXT_CHARS,
            )
        }
    };
    result.text_notes.push(text);
    Ok(result)
}

/// Ошибка одного вложения становится пометкой и не прерывает остальные.
pub fn build_attachment_message_parts(attachments: &[(String, String)]) -> AttachmentParts {
    let mut parts = AttachmentParts::default();
    for (name, path) in attachments.iter().take(10) {
        match read_attachment(Path::new(path)) {
            Ok(item) => {
                parts.text_notes.extend(
                    item.text_notes
                        .into_iter()
                        .map(|s| format!("--- Файл «{name}» ---\n{s}")),
                );
                parts.images.extend(item.images);
            }
            Err(error) => parts
                .text_notes
                .push(format!("[Ошибка чтения «{name}»: {error}]")),
        }
    }
    parts
}

/// Собственная копия нужна для Android content:// и для истории после удаления исходника.
pub fn store_material(name: &str, bytes: &[u8]) -> Result<(String, String)> {
    ensure!(
        bytes.len() as u64 <= MAX_FILE_BYTES,
        "Размер вложения превышает 32 МиБ"
    );
    let name = Path::new(name)
        .file_name()
        .context("У файла нет имени")?
        .to_string_lossy()
        .into_owned();
    let dir = super::paths::app_data_dir()?
        .join("materials")
        .join(uuid::Uuid::new_v4().to_string());
    std::fs::create_dir_all(&dir)?;
    let path = dir.join(&name);
    std::fs::write(&path, bytes)?;
    Ok((name, path.to_string_lossy().into_owned()))
}

pub fn import_material(name: &str, path: &Path) -> Result<(String, String)> {
    ensure!(
        path.is_file() && path.metadata()?.len() <= MAX_FILE_BYTES,
        "Выберите файл до 32 МиБ"
    );
    let mut bytes = Vec::new();
    std::fs::File::open(path)?
        .take(MAX_FILE_BYTES + 1)
        .read_to_end(&mut bytes)?;
    store_material(name, &bytes)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn unicode_limit_does_not_cut_a_codepoint() {
        assert_eq!(truncate("Привет", 3), "При\n…[обрезано]");
    }
    #[test]
    fn missing_file_does_not_hide_other_attachments() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("code.rs");
        std::fs::write(&path, "fn main() {}").unwrap();
        let result = build_attachment_message_parts(&[
            ("lost".into(), "/missing/xopilot".into()),
            ("code".into(), path.to_string_lossy().into_owned()),
        ]);
        assert_eq!(result.text_notes.len(), 2);
        assert!(result.text_notes[1].contains("fn main"));
    }
    #[test]
    fn invalid_image_is_not_sent_to_a_model() {
        assert!(downscale_image_bytes(b"not an image").is_err());
    }
}
