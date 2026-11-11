// Описание: Одна кнопка проводника для Desktop и системного Android chooser.
use crate::{
    app::{
        shared::icons,
        state::{self, AppState},
    },
    services::{self, model_import},
};
use dioxus::prelude::*;

#[component]
/// Определяет вариант модели по содержимому выбранного файла, без ручного пути.
pub fn build_model_import() -> Element {
    let state = use_context::<Signal<AppState>>();
    let mut working = use_signal(|| false);
    use_future(move || async move {
        if !cfg!(target_os = "android") {
            return;
        }
        use services::mobile_documents::UploadEvent;
        let script = include_str!("model_picker.js");
        let mut bridge = document::eval(script);
        let mut upload = None::<model_import::Upload>;
        while let Ok(event) = bridge.recv::<UploadEvent>().await {
            // Сообщение об ошибке JS не является запросом: лишний ack испортит следующий импорт.
            if let UploadEvent::Error { message } = event {
                upload = None;
                working.set(false);
                model_import::fail(message.clone());
                state::report(state, Err(anyhow::anyhow!(message)));
                continue;
            }
            let result: anyhow::Result<()> = async {
                match event {
                    UploadEvent::Start { size, .. } => {
                        upload = Some(
                            services::runtime::blocking(move || {
                                model_import::Upload::start(size as u64)
                            })
                            .await?,
                        );
                        working.set(true);
                    }
                    UploadEvent::Chunk { data } => {
                        use base64::Engine as _;
                        anyhow::ensure!(data.len() <= 90_000, "Слишком большой блок модели");
                        let bytes = base64::prelude::BASE64_STANDARD.decode(data)?;
                        let mut current = upload
                            .take()
                            .ok_or_else(|| anyhow::anyhow!("Передача не началась"))?;
                        upload = Some(
                            services::runtime::blocking(move || {
                                current.push(&bytes)?;
                                Ok(current)
                            })
                            .await?,
                        );
                    }
                    UploadEvent::End => {
                        let current = upload
                            .take()
                            .ok_or_else(|| anyhow::anyhow!("Передача не началась"))?;
                        services::runtime::blocking(move || current.finish()).await?;
                    }
                    UploadEvent::Done => {
                        working.set(false);
                        return Ok(());
                    }
                    UploadEvent::Error { .. } => unreachable!(),
                }
                bridge.send(true)?;
                Ok(())
            }
            .await;
            if let Err(error) = result {
                let _ = bridge.send(serde_json::json!({"error": error.to_string()}));
                upload = None;
                working.set(false);
                model_import::fail(error.to_string());
                state::report(state, Err(error));
            }
        }
    });
    use_drop(move || {
        document::eval("window.__xopilotModelPicker?.abort();");
    });
    rsx! {
        label {
            class: "button model-import-trigger",
            title: "Импорт модели из файла",
            icons::build_icon {
                name: "folder_open",
            }
            span {
                if *working.read() {
                    "Импорт модели…"
                } else {
                    "Импорт модели из файла"
                }
            }
            input {
                id: "model-file-picker",
                r#type: "file",
                accept: ".litertlm",
                disabled: *working.read(),
                onchange: move |event| {
                    if cfg!(target_os = "android") {
                        return;
                    }
                    let Some(file) = event.files().into_iter().next() else {
                        return;
                    };
                    let path = file.path();
                    working.set(true);
                    spawn(async move {
                        let result = services::runtime::blocking(move || model_import::import_file(
                                &path,
                            ))
                            .await
                            .map(|_| ());
                        working.set(false);
                        state::report(state, result);
                    });
                },
            }
        }
    }
}
