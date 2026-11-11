// Описание: Проверка настоящего WebKit-интерфейса через события DOM.
// Мост существует только в этом примере; в пользовательской сборке его нет.
// Запускать с отдельными XOPILOT_DATA_DIR и XOPILOT_UI_SOCKET в каталоге 0700.
#[cfg(target_os = "linux")]
use dioxus::prelude::*;
#[cfg(target_os = "linux")]
use std::{
    io::{BufRead, BufReader, Write},
    os::unix::net::UnixListener,
};

#[cfg(target_os = "linux")]
struct Command {
    script: String,
    response: tokio::sync::oneshot::Sender<serde_json::Value>,
}

#[cfg(not(target_os = "linux"))]
fn main() {
    eprintln!("Этот стенд проверяет Linux WebKitGTK. Запускайте его на Linux.");
}

#[cfg(target_os = "linux")]
fn main() {
    assert!(
        std::env::var_os("XOPILOT_DATA_DIR").is_some(),
        "Нужна отдельная тестовая база"
    );
    let socket = std::env::var_os("XOPILOT_UI_SOCKET").expect("Нужен тестовый Unix socket");
    let listener = UnixListener::bind(socket).expect("Не удалось открыть тестовый socket");
    let (tx, rx) = tokio::sync::mpsc::unbounded_channel::<Command>();
    std::thread::spawn(move || {
        for connection in listener.incoming() {
            let Ok(mut connection) = connection else {
                continue;
            };
            let mut reader = BufReader::new(connection.try_clone().unwrap());
            let mut line = String::new();
            while reader.read_line(&mut line).unwrap_or_default() > 0 {
                let Ok(script) = serde_json::from_str::<String>(&line) else {
                    break;
                };
                line.clear();
                let (response, reply) = tokio::sync::oneshot::channel();
                if tx.send(Command { script, response }).is_err() {
                    break;
                }
                let result = reply.blocking_recv().unwrap_or(serde_json::Value::Null);
                if writeln!(connection, "{result}").is_err() {
                    break;
                }
            }
        }
    });
    // Receiver принадлежит одному компоненту и не требует глобального состояния.
    let rx = std::sync::Arc::new(std::sync::Mutex::new(Some(rx)));
    dioxus::LaunchBuilder::desktop()
        .with_cfg(
            dioxus::desktop::Config::new().with_menu(None).with_window(
                dioxus::desktop::WindowBuilder::new()
                    .with_title("Xopilot · UI test")
                    .with_inner_size(dioxus::desktop::LogicalSize::new(1060.0, 760.0)),
            ),
        )
        .with_context(rx)
        .launch(build_test_app);
}

#[cfg(target_os = "linux")]
fn build_test_app() -> Element {
    let rx = use_context::<
        std::sync::Arc<std::sync::Mutex<Option<tokio::sync::mpsc::UnboundedReceiver<Command>>>>,
    >();
    use_future(move || {
        let mut receiver = rx.lock().unwrap().take().expect("Единственный мост");
        async move {
            while let Some(command) = receiver.recv().await {
                let script = format!(
                    "const result=await(async()=>{{try {{ {} }} catch (error) {{ return {{__ui_error:String(error),stack:error.stack}}; }} }})();dioxus.send(result);await dioxus.recv();",
                    command.script
                );
                // Держим JS-query до подтверждения Rust. Иначе GC WebKit может
                // освободить завершённый eval до пробуждения его Rust future.
                let mut evaluation = document::eval(&script);
                let value = match evaluation.recv::<serde_json::Value>().await {
                    Ok(value) => serde_json::json!({"value": value}),
                    Err(error) => serde_json::json!({"error": format!("{error:?}")}),
                };
                let _ = evaluation.send(true);
                let _ = command.response.send(value);
            }
        }
    });
    rsx! { xopilot::app::main::build_app_ui {} }
}
