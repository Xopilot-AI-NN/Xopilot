// Описание: Создание DOCX и XLSX средствами Rust, без внешнего офисного приложения.
use anyhow::{Result, ensure};
use std::{io::Write, path::PathBuf};

/// Экранирует пользовательский текст для XML. Таблица хранит строки, формулы не исполняются.
fn escaped(text: &str) -> String {
    quick_xml::escape::escape(text).into_owned()
}

/// Создаёт переносимый документ OOXML и атомарно публикует его в exports.
pub fn save(title: &str, content: &str, format: &str) -> Result<PathBuf> {
    let root = super::paths::app_data_dir()?.join("exports");
    save_at(&root, title, content, format)
}

/// Принимает выбранный каталог. TSV преобразуется в строки и столбцы XLSX.
pub fn save_at(
    root: &std::path::Path,
    title: &str,
    content: &str,
    format: &str,
) -> Result<PathBuf> {
    ensure!(["docx", "xlsx"].contains(&format), "Выберите DOCX или XLSX");
    ensure!(content.len() <= 1024 * 1024, "Документ превышает 1 МиБ");
    ensure!(
        title.chars().chain(content.chars()).all(|character| {
            matches!(character, '\t' | '\n' | '\r')
                || (character >= ' ' && character != '\u{fffe}' && character != '\u{ffff}')
        }),
        "Документ содержит недопустимые символы XML"
    );
    std::fs::create_dir_all(root)?;
    let output = root.join(format!("document-{}.{format}", uuid::Uuid::new_v4()));
    let mut temporary = tempfile::NamedTempFile::new_in(root)?;
    {
        let mut archive = zip::ZipWriter::new(temporary.as_file_mut());
        let mut write = |name: &str, text: &str| -> Result<()> {
            archive.start_file(name, zip::write::SimpleFileOptions::default())?;
            archive.write_all(text.as_bytes())?;
            Ok(())
        };
        let (part, kind) = if format == "docx" {
            ("word/document.xml", "wordprocessingml.document")
        } else {
            ("xl/workbook.xml", "spreadsheetml.sheet")
        };
        write(
            "[Content_Types].xml",
            &format!(
                r#"<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/{part}" ContentType="application/vnd.openxmlformats-officedocument.{kind}.main+xml"/>{}</Types>"#,
                if format == "xlsx" {
                    r#"<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>"#
                } else {
                    ""
                }
            ),
        )?;
        write(
            "_rels/.rels",
            &format!(
                r#"<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="{part}"/></Relationships>"#
            ),
        )?;
        if format == "docx" {
            let paragraphs = std::iter::once(title)
                .chain(content.lines())
                .map(|line| {
                    format!(
                        "<w:p><w:r><w:t xml:space=\"preserve\">{}</w:t></w:r></w:p>",
                        escaped(line)
                    )
                })
                .collect::<String>();
            write(
                part,
                &format!(
                    r#"<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{paragraphs}<w:sectPr/></w:body></w:document>"#
                ),
            )?;
        } else {
            write(
                part,
                r#"<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Лист 1" sheetId="1" r:id="rId1"/></sheets></workbook>"#,
            )?;
            write(
                "xl/_rels/workbook.xml.rels",
                r#"<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>"#,
            )?;
            let mut rows = String::new();
            for (row, line) in content.lines().enumerate() {
                rows.push_str(&format!("<row r=\"{}\">", row + 1));
                for (column, value) in line.split('\t').enumerate() {
                    ensure!(column < 16384 && row < 100000, "Превышен размер таблицы");
                    rows.push_str(&format!(
                        "<c t=\"inlineStr\"><is><t xml:space=\"preserve\">{}</t></is></c>",
                        escaped(value)
                    ));
                }
                rows.push_str("</row>");
            }
            write(
                "xl/worksheets/sheet1.xml",
                &format!(
                    r#"<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{rows}</sheetData></worksheet>"#
                ),
            )?;
        }
        archive.finish()?;
    }
    temporary.as_file().sync_all()?;
    temporary.persist(&output).map_err(|error| error.error)?;
    Ok(output)
}
