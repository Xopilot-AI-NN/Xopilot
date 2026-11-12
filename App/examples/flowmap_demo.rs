// Создано ChatGPT: демонстрация реальной карты выполнения Rust для Xopilot.
// Демо записывает только собственный временный файл и автоматически удаляет его.

use std::io;
use xopilot::flow_trace as trace;

fn main() -> io::Result<()> {
    trace::begin("Запуск демонстрации");
    let temporary = tempfile::NamedTempFile::new()?;
    trace::step("Создан временный файл");

    trace::call("std::fs::write");
    trace::write(temporary.path(), "Привет, мир!")?;

    trace::call("std::fs::read_to_string");
    let content = trace::read_to_string(temporary.path())?;
    let testingss = content.len();
    trace::variable("testingss", &testingss);

    let has_data = testingss > 0;
    trace::decision("testingss > 0", has_data);
    if has_data {
        trace::step("Полученные данные не пусты");
    } else {
        trace::error(
            "Пустой файл",
            &"Файл не содержал данных",
        );
    }

    println!("Прочитано {testingss} байт");
    trace::end("Завершение демонстрации");
    Ok(())
}
