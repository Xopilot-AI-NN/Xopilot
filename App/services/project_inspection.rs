// Файл: App/services/project_inspection.rs
// Описание: Чтение и поиск внутри выбранной папки; Git только для просмотра.
use anyhow::{Context, Result, ensure};
use serde::{Deserialize, Serialize};
use std::{
    io::Read,
    path::{Path, PathBuf},
};

pub const MAX_FILE: u64 = 1024 * 1024;

/// Канонический путь проверяем после раскрытия симлинков.
pub fn resolve(
    root: &Path,
    relative: &str,
) -> Result<PathBuf> {
    let root = root
        .canonicalize()
        .context("Папка проекта недоступна")?;
    let relative = Path::new(relative);
    ensure!(
        !relative.is_absolute(),
        "Нужен путь относительно папки проекта"
    );
    ensure!(
        !relative.components().any(|c| matches!(
            c,
            std::path::Component::ParentDir
        )),
        "Выход за пределы проекта запрещён"
    );
    ensure!(
        !relative.components().any(|c| {
            let name = c.as_os_str().to_string_lossy();
            name.starts_with('.')
                && ![
                    ".github",
                    ".gitignore",
                    ".env.example",
                ]
                .contains(&name.as_ref())
        }),
        "Скрытый личный файл недоступен"
    );
    let full = root
        .join(relative)
        .canonicalize()
        .context("Файл проекта не найден")?;
    ensure!(
        full.starts_with(&root),
        "Ссылка ведёт за пределы проекта"
    );
    Ok(full)
}

/// Читает ограниченный текстовый файл внутри выбранного проекта.
pub fn read_text(
    root: &Path,
    relative: &str,
) -> Result<String> {
    let path = resolve(root, relative)?;
    ensure!(
        path.metadata()?.len() <= MAX_FILE,
        "Файл больше 1 МиБ"
    );
    let mut bytes = Vec::new();
    std::fs::File::open(path)?
        .take(MAX_FILE + 1)
        .read_to_end(&mut bytes)?;
    ensure!(
        bytes.len() as u64 <= MAX_FILE
            && !bytes.contains(&0),
        "Файл слишком большой или двоичный"
    );
    String::from_utf8(bytes).context("Файл не в UTF-8")
}

#[derive(
    Clone, Debug, PartialEq, Serialize, Deserialize,
)]
pub struct SearchHit {
    pub path: String,
    pub line: usize,
    pub text: String,
}

/// Обходит доступные файлы проекта, исключая служебные и скрытые каталоги.
pub fn list_files(root: &Path) -> Result<Vec<String>> {
    let root = root.canonicalize()?;
    let mut result = Vec::new();
    let mut pending = vec![(root.clone(), 0)];
    while let Some((dir, depth)) = pending.pop() {
        if depth > 16 {
            continue;
        }
        for entry in std::fs::read_dir(dir)? {
            let entry = entry?;
            let file_type = entry.file_type()?;
            let name = entry
                .file_name()
                .to_string_lossy()
                .into_owned();
            if file_type.is_symlink()
                || [
                    "target",
                    "node_modules",
                    "build",
                    "venv",
                    "__pycache__",
                ]
                .contains(&name.as_str())
            {
                continue;
            }
            if name.starts_with('.')
                && ![
                    ".github",
                    ".gitignore",
                    ".env.example",
                ]
                .contains(&name.as_str())
            {
                continue;
            }
            if file_type.is_dir() {
                pending.push((entry.path(), depth + 1));
            } else if file_type.is_file()
                && entry.metadata()?.len() <= MAX_FILE
            {
                result.push(
                    entry
                        .path()
                        .strip_prefix(&root)?
                        .to_string_lossy()
                        .into_owned(),
                );
            }
            if result.len() >= 10_000 {
                result.sort();
                return Ok(result);
            }
        }
    }
    result.sort();
    Ok(result)
}

/// Ищет текст в разрешённых файлах выбранного проекта.
pub fn search(
    root: &Path,
    query: &str,
) -> Result<Vec<SearchHit>> {
    ensure!(!query.is_empty(), "Введите текст для поиска");
    let query = query.to_lowercase();
    let mut hits = Vec::new();
    for path in list_files(root)? {
        let Ok(text) = read_text(root, &path) else {
            continue;
        };
        for (line, text) in text.lines().enumerate() {
            if text.to_lowercase().contains(&query) {
                hits.push(SearchHit {
                    path: path.clone(),
                    line: line + 1,
                    text: super::attachments::truncate(
                        text, 300,
                    ),
                });
            }
            if hits.len() >= 200 {
                return Ok(hits);
            }
        }
    }
    Ok(hits)
}

/// Получает состояние Git выбранного проекта без изменения файлов.
pub async fn git(
    root: &Path,
    diff: bool,
) -> Result<String> {
    let mut command = tokio::process::Command::new("git");
    command
        .args([
            "--no-optional-locks",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=/dev/null",
            "-C",
        ])
        .arg(root)
        .kill_on_drop(true);
    if diff {
        command.args([
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--stat",
        ]);
    } else {
        command.args(["status", "--short"]);
    }
    let output = tokio::time::timeout(
        std::time::Duration::from_secs(15),
        command.output(),
    )
    .await??;
    ensure!(
        output.status.success(),
        "Git: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    Ok(super::attachments::truncate(
        &String::from_utf8_lossy(&output.stdout),
        50_000,
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    /// Проверяет запрет выхода за папку проекта и чтения скрытых секретов.
    #[test]
    fn cannot_read_parent_or_hidden_secret() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join(".env"), "secret")
            .unwrap();
        assert!(resolve(dir.path(), ".env").is_err());
        assert!(resolve(dir.path(), "../.env").is_err());
    }
    /// Проверяет защиту от выхода через символическую ссылку.
    #[cfg(unix)]
    #[test]
    fn cannot_escape_through_symlink() {
        let dir = tempfile::tempdir().unwrap();
        let outside = tempfile::tempdir().unwrap();
        std::fs::write(
            outside.path().join("secret"),
            "secret",
        )
        .unwrap();
        std::os::unix::fs::symlink(
            outside.path().join("secret"),
            dir.path().join("link"),
        )
        .unwrap();
        assert!(read_text(dir.path(), "link").is_err());
    }
}
