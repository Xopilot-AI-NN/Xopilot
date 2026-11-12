// Проверяем реальные файлы, которые затем читает тот же тракт вложений приложения.
use xopilot::services::{attachments, diagnostics, office, spreadsheets};

#[test]
fn office_files_preserve_unicode_and_do_not_execute_formula_strings() {
    let root = tempfile::tempdir().unwrap();
    let content = "Привет & мир\t=1+1\nРусский текст\t42";
    let sheet = office::save_at(root.path(), "Таблица", content, "xlsx").unwrap();
    let text = spreadsheets::read(&std::fs::read(&sheet).unwrap()).unwrap();
    assert!(text.contains("Привет & мир"));
    assert!(text.contains("=1+1"));
    let doc = office::save_at(root.path(), "Документ", content, "docx").unwrap();
    let parts = attachments::build_attachment_message_parts(&[(
        "report.docx".into(),
        doc.to_string_lossy().into_owned(),
    )]);
    assert!(parts.text_notes[0].contains("Привет & мир"));
    assert!(office::save_at(root.path(), "test", "text", "exe").is_err());
}

#[test]
fn diagnostic_snapshot_contains_only_technical_fields() {
    let snapshot = diagnostics::snapshot();
    let object = snapshot.as_object().unwrap();
    assert_eq!(object.len(), 6);
    assert_eq!(snapshot["application"], "Xopilot");
    assert!(!object.contains_key("messages"));
    assert!(!object.contains_key("api_key"));
}
