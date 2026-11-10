// Файл: App/services/mobile_documents.rs
// Описание: Ограниченный протокол передачи файлов Android WebView → Rust.
// Dioxus Desktop 0.7.10 возвращает пустой список из своего диалога на Android,
// поэтому используем системный chooser WebView и передаём данные небольшими чанками.
use anyhow::{Result, ensure};
use base64::{Engine, prelude::BASE64_STANDARD};
use serde::Deserialize;

pub const PICKER_SCRIPT: &str = include_str!("mobile_documents.js");

#[derive(Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum UploadEvent {
    Start { name: String, size: usize },
    Chunk { data: String },
    End,
    Done,
    Error { message: String },
}

#[derive(Default)]
pub struct Upload {
    name: String,
    expected: Option<usize>,
    bytes: Vec<u8>,
}

impl Upload {
    pub fn start(&mut self, name: String, size: usize) -> Result<()> {
        ensure!(self.expected.is_none(), "Предыдущий файл ещё передаётся");
        ensure!(
            size as u64 <= super::attachments::MAX_FILE_BYTES,
            "Размер файла превышает 32 МиБ"
        );
        self.name = name;
        self.expected = Some(size);
        self.bytes.clear();
        Ok(())
    }

    pub fn chunk(&mut self, data: &str) -> Result<()> {
        let expected = self
            .expected
            .ok_or_else(|| anyhow::anyhow!("Передача файла не начата"))?;
        ensure!(data.len() <= 90_000, "Слишком большой чанк файла");
        let bytes = BASE64_STANDARD.decode(data)?;
        ensure!(
            self.bytes.len() + bytes.len() <= expected,
            "Получено больше данных, чем указано в размере файла"
        );
        self.bytes.extend_from_slice(&bytes);
        Ok(())
    }

    pub fn finish(&mut self) -> Result<(String, Vec<u8>)> {
        ensure!(
            self.expected == Some(self.bytes.len()),
            "Файл передан не полностью"
        );
        self.expected = None;
        Ok((
            std::mem::take(&mut self.name),
            std::mem::take(&mut self.bytes),
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn upload_requires_declared_size_and_accepts_chunked_unicode_file() {
        let mut upload = Upload::default();
        assert!(upload.chunk("YWJj").is_err());
        upload.start("текст.md".into(), 6).unwrap();
        upload
            .chunk(&BASE64_STANDARD.encode("При".as_bytes()))
            .unwrap();
        let (name, data) = upload.finish().unwrap();
        assert_eq!(name, "текст.md");
        assert_eq!(String::from_utf8(data).unwrap(), "При");
        assert!(
            upload
                .start(
                    "large".into(),
                    super::super::attachments::MAX_FILE_BYTES as usize + 1
                )
                .is_err()
        );
    }
    #[test]
    fn truncated_and_oversized_payloads_are_rejected() {
        let mut upload = Upload::default();
        upload.start("file".into(), 2).unwrap();
        upload.chunk(&BASE64_STANDARD.encode(b"a")).unwrap();
        assert!(upload.finish().is_err());
        assert!(upload.chunk(&BASE64_STANDARD.encode(b"bc")).is_err());
    }
}
