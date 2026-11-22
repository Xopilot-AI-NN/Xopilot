// Закрытый мост Linux WebKit для UI-тестов основного приложения.
use dioxus::prelude::*;
use std::{
    io::{BufRead, BufReader, Write},
    os::unix::{fs::PermissionsExt, net::UnixListener},
    path::PathBuf,
};

struct Command {
    script: String,
    response:
        tokio::sync::oneshot::Sender<serde_json::Value>,
}

/// Обычный запуск dev-сборки использует тестовые данные и не открывает сокет.
pub fn launch(launcher: dioxus::LaunchBuilder) {
    let Some(socket) =
        std::env::var_os("XOPILOT_UI_SOCKET")
            .map(PathBuf::from)
    else {
        launcher.launch(xopilot::app::main::build_app_ui);
        return;
    };
    assert!(
        std::env::var_os("XOPILOT_DATA_DIR").is_some(),
        "Нужна отдельная тестовая база"
    );
    let parent =
        socket.parent().expect("Нужен каталог сокета");
    let metadata = std::fs::metadata(parent)
        .expect("Нет каталога сокета");
    assert!(
        metadata.is_dir()
            && metadata.permissions().mode() & 0o777
                == 0o700,
        "Каталог тестового сокета должен иметь права 0700"
    );
    let listener = UnixListener::bind(socket)
        .expect("Не удалось открыть тестовый socket");
    let (tx, rx) =
        tokio::sync::mpsc::unbounded_channel::<Command>();
    std::thread::spawn(move || {
        for connection in listener.incoming() {
            let Ok(mut connection) = connection else {
                continue;
            };
            let mut reader = BufReader::new(
                connection.try_clone().unwrap(),
            );
            let mut line = String::new();
            while reader
                .read_line(&mut line)
                .unwrap_or_default()
                > 0
            {
                let Ok(script) =
                    serde_json::from_str::<String>(&line)
                else {
                    break;
                };
                line.clear();
                let (response, reply) =
                    tokio::sync::oneshot::channel();
                if tx
                    .send(Command { script, response })
                    .is_err()
                {
                    break;
                }
                let result = reply
                    .blocking_recv()
                    .unwrap_or(serde_json::Value::Null);
                if writeln!(connection, "{result}").is_err()
                {
                    break;
                }
            }
        }
    });
    // Receiver принадлежит одному компоненту и не требует глобального состояния.
    let rx = std::sync::Arc::new(std::sync::Mutex::new(
        Some(rx),
    ));
    launcher.with_context(rx).launch(build_test_app);
}

/// Собирает изолированное состояние интерфейса для проверки.
fn build_test_app() -> Element {
    let rx = use_context::<
        std::sync::Arc<
            std::sync::Mutex<
                Option<
                    tokio::sync::mpsc::UnboundedReceiver<
                        Command,
                    >,
                >,
            >,
        >,
    >();
    use_future(move || {
        let mut receiver = rx
            .lock()
            .unwrap()
            .take()
            .expect("Единственный мост");
        async move {
            while let Some(command) = receiver.recv().await
            {
                let script = format!(
                    "const result=await(async()=>{{try {{ {} }} catch (error) {{ return {{__ui_error:String(error),stack:error.stack}}; }} }})();dioxus.send(result);await dioxus.recv();",
                    command.script
                );
                // Держим JS-query до подтверждения Rust. Иначе GC WebKit может
                // освободить завершённый eval до пробуждения его Rust future.
                let mut evaluation =
                    document::eval(&script);
                let value = match evaluation
                    .recv::<serde_json::Value>()
                    .await
                {
                    Ok(value) => {
                        serde_json::json!({"value": value})
                    }
                    Err(error) => {
                        serde_json::json!({"error": format!("{error:?}")})
                    }
                };
                let _ = evaluation.send(true);
                let _ = command.response.send(value);
            }
        }
    });
    rsx! {
        xopilot::app::main::build_app_ui {

        }
    }
}
