// Описание: Один файл из проводника определяется по SHA-256 и устанавливается атомарно.
use anyhow::{Context, Result, ensure};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    io::{Read, Write},
    path::Path,
    sync::{Mutex, OnceLock},
};

#[derive(
    Clone, Default, PartialEq, Serialize, Deserialize,
)]
pub struct Progress {
    pub phase: String,
    pub received: u64,
    pub total: u64,
    pub message: String,
}
static RUNNING: std::sync::atomic::AtomicBool =
    std::sync::atomic::AtomicBool::new(false);
static PROGRESS: OnceLock<Mutex<Progress>> =
    OnceLock::new();
/// Возвращает снимок импорта, в том числе после закрытия окна моделей.
pub fn progress() -> Progress {
    PROGRESS
        .get_or_init(Default::default)
        .lock()
        .map(|p| p.clone())
        .unwrap_or_default()
}
/// Публикует состояние операции без обращения к сигналам интерфейса из worker.
fn publish(value: Progress) {
    if let Ok(mut current) =
        PROGRESS.get_or_init(Default::default).lock()
    {
        *current = value;
    }
}
/// Запоминает ошибку, чтобы она была видна в общем блоке прогресса.
pub fn fail(message: String) {
    if RUNNING.load(std::sync::atomic::Ordering::Acquire) {
        return;
    }
    let mut value = progress();
    value.phase = "error".into();
    value.message = message;
    publish(value);
}
/// Закрывает завершённое уведомление импорта, не затрагивая установленный файл.
pub fn dismiss() {
    if !matches!(
        progress().phase.as_str(),
        "copying" | "verifying"
    ) {
        publish(Progress::default());
    }
}

pub struct Upload {
    file: Option<tempfile::NamedTempFile>,
    expected: u64,
    received: u64,
    hash: Sha256,
    finished: bool,
}
impl Upload {
    /// Резервирует временный файл на диске моделей, а не гигабайты в оперативной памяти.
    pub fn start(size: u64) -> Result<Self> {
        Self::start_in(super::paths::models_dir()?, size)
    }
    /// Позволяет проверять передачу в отдельном каталоге без личных файлов.
    fn start_in(
        root: std::path::PathBuf,
        size: u64,
    ) -> Result<Self> {
        ensure!(
            size > 0 && size <= 8 * 1024 * 1024 * 1024,
            "Модель должна занимать от 1 байта до 8 ГиБ"
        );
        std::fs::create_dir_all(&root)?;
        ensure!(
            fs2::available_space(&root)?
                > size + 64 * 1024 * 1024,
            "Недостаточно места для выбранной модели"
        );
        let mut current = PROGRESS
            .get_or_init(Default::default)
            .lock()
            .map_err(|_| {
                anyhow::anyhow!("Импорт недоступен")
            })?;
        ensure!(
            !matches!(
                current.phase.as_str(),
                "copying" | "verifying"
            ),
            "Дождитесь текущего импорта"
        );
        ensure!(
            !RUNNING.swap(
                true,
                std::sync::atomic::Ordering::AcqRel
            ),
            "Дождитесь текущего импорта"
        );
        let file =
            match tempfile::NamedTempFile::new_in(root) {
                Ok(file) => file,
                Err(error) => {
                    RUNNING.store(
                    false,
                    std::sync::atomic::Ordering::Release,
                );
                    return Err(error.into());
                }
            };
        *current = Progress {
            phase: "copying".into(),
            total: size,
            message: "Копируем и проверяем модель".into(),
            ..Default::default()
        };
        Ok(Self {
            file: Some(file),
            expected: size,
            received: 0,
            hash: Sha256::new(),
            finished: false,
        })
    }
    /// Принимает ограниченный блок; контроль размера запрещает переполнение заявленного файла.
    pub fn push(&mut self, bytes: &[u8]) -> Result<()> {
        ensure!(
            bytes.len() <= 1024 * 1024
                && self.received + bytes.len() as u64
                    <= self.expected,
            "Неверный размер блока модели"
        );
        self.file
            .as_mut()
            .context("Передача уже завершена")?
            .write_all(bytes)?;
        self.hash.update(bytes);
        self.received += bytes.len() as u64;
        publish(Progress {
            phase: "copying".into(),
            received: self.received,
            total: self.expected,
            message: "Копируем и проверяем модель".into(),
        });
        Ok(())
    }
    /// Сравнивает содержимое с каталогом и публикует готовый файл одним переименованием.
    pub fn finish(mut self) -> Result<String> {
        ensure!(
            self.received == self.expected,
            "Передача модели оборвалась"
        );
        let digest =
            hex::encode(self.hash.clone().finalize());
        let model = super::model_installer::MODELS
            .iter()
            .copied()
            .find(|m| m.sha256 == digest)
            .context(
                "Файл не совпадает с поддерживаемыми Gemma: проверьте оригинальный .litertlm",
            )?;
        let mut file = self
            .file
            .take()
            .context("Файл импорта утрачен")?;
        file.flush()?;
        file.as_file().sync_all()?;
        super::model_installer::install_staged(
            model, file,
        )?;
        self.finished = true;
        publish(Progress {
            phase: "installed".into(),
            received: self.received,
            total: self.expected,
            message: format!(
                "{} готова к работе",
                model.name
            ),
        });
        Ok(model.name.into())
    }
}
impl Drop for Upload {
    /// Незавершённый content URI никогда не оставляет частичную модель в каталоге.
    fn drop(&mut self) {
        if !self.finished {
            let mut value = progress();
            if value.phase == "copying" {
                value.phase = "cancelled".into();
                value.message = "Импорт не завершён".into();
                publish(value);
            }
        }
        RUNNING.store(
            false,
            std::sync::atomic::Ordering::Release,
        );
    }
}
/// Читает выбранный Desktop-файл блоками; имя файла не влияет на определение модели.
pub fn import_file(path: &Path) -> Result<String> {
    let result = (|| {
        let mut source = std::fs::File::open(path)?;
        let mut upload =
            Upload::start(source.metadata()?.len())?;
        let mut bytes = vec![0; 1024 * 1024];
        loop {
            let count = source.read(&mut bytes)?;
            if count == 0 {
                break;
            }
            upload.push(&bytes[..count])?;
        }
        upload.finish()
    })();
    if let Err(error) = &result {
        fail(format!("{error:#}"));
    }
    result
}

#[cfg(test)]
mod tests {
    /// Оборванный и чужой файл не заменяют установленные веса и не оставляют временных копий.
    #[test]
    fn truncated_or_unknown_model_preserves_installed_file()
    {
        let dir = tempfile::tempdir().unwrap();
        let original = dir.path().join(
            super::super::model_installer::MODELS[0]
                .filename,
        );
        std::fs::write(&original, b"original").unwrap();
        let mut upload = super::Upload::start_in(
            dir.path().to_path_buf(),
            10,
        )
        .unwrap();
        upload.push(b"abc").unwrap();
        assert!(upload.finish().is_err());
        let mut upload = super::Upload::start_in(
            dir.path().to_path_buf(),
            3,
        )
        .unwrap();
        assert!(upload.push(b"overflow").is_err());
        upload.push(b"abc").unwrap();
        assert!(upload.finish().is_err());
        assert_eq!(
            std::fs::read(&original).unwrap(),
            b"original"
        );
        assert_eq!(
            std::fs::read_dir(dir.path()).unwrap().count(),
            1
        );
    }
}
