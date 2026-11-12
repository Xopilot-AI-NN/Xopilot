// Описание: Системный выбор файлов Dioxus; одинаковый поток для ПК и Android.
use crate::app::shared::icons;
use crate::{
    app::state::{self, AppState},
    services,
};
use dioxus::prelude::*;

/// Открывает проводник и добавляет выбранные материалы в черновик.
#[component]
pub fn build_add_material_button() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let mut loading = use_signal(|| false);
    use_drop(move || {
        if let Ok(mut value) = state.try_write() {
            value.uploading = false;
        }
    });
    rsx! {
        label {
            class: "file-button brand-button tone-create",
            title: "Добавить материал",
            "aria-label": "Добавить материал",
            icons::build_icon {
                name: if *loading.read() { "hourglass_empty" } else { "add" },
            }
            input {
                r#type: "file",
                multiple: true,
                disabled: *loading.read() || state.read().busy,
                onchange: move |event| {
                    let files = event.files();
                    let active = state.read().active;
                    loading.set(true);
                    state.write().uploading = true;
                    spawn(async move {
                        let result = async {
                            anyhow::ensure!(
                                state.read().draft.files.len() + files.len() <= 10,
                                "К сообщению можно прикрепить до 10 файлов"
                            ); // Поздний ответ файлового диалога не прикрепляется к другому чату.
                            for file in files {
                                anyhow::ensure!(
                                    file.size() <= services::attachments::MAX_FILE_BYTES,
                                    "Размер файла превышает 32 МиБ"
                                );
                                let name = file.name();
                                let path = file.path();
                                let material = services::runtime::blocking(move || services::attachments::import_material(
                                        &name,
                                        &path,
                                    ))
                                    .await?;
                                if state.read().active == active {
                                    state.write().draft.files.push(material);
                                }
                            }
                            state::persist_draft(state).await
                        }
                            .await;
                        loading.set(false);
                        state.write().uploading = false;
                        state::report(state, result);
                    });
                },
            }
        }
    }
}

/// Android использует системный файловый chooser WebView: не rfd и не Flutter.
#[component]
pub fn build_android_material_button() -> Element {
    use crate::services::mobile_documents::{
        Upload, UploadEvent,
    };
    let mut state = use_context::<Signal<AppState>>();
    use_drop(move || {
        if let Ok(mut value) = state.try_write() {
            value.uploading = false;
        }
    });
    use_future(move || async move {
        let mut bridge = document::eval(
            services::mobile_documents::PICKER_SCRIPT,
        );
        let mut upload = Upload::default();
        let mut active = None;
        while let Ok(event) =
            bridge.recv::<UploadEvent>().await
        {
            let expects_ack = matches!(
                &event,
                UploadEvent::Start { .. }
                    | UploadEvent::Chunk { .. }
                    | UploadEvent::End
            );
            let result = async {
                match event {
                    UploadEvent::Start { name, size } => {
                        anyhow::ensure!(!state.read().busy, "Дождитесь ответа модели");
                        anyhow::ensure!(
                            state.read().draft.files.len() < 10,
                            "К сообщению можно прикрепить до 10 файлов"
                        );
                        active = state.read().active;
                        state.write().uploading = true;
                        upload.start(name, size)?;
                        bridge.send(true)?;
                    }
                    UploadEvent::Chunk { data } => {
                        upload.chunk(&data)?;
                        bridge.send(true)?;
                    }
                    UploadEvent::End => {
                        let (name, bytes) = upload.finish()?;
                        let material = services::runtime::blocking(move || {
                            services::attachments::store_material(&name, &bytes)
                        })
                        .await?;
                        if state.read().active == active {
                            state.write().draft.files.push(material);
                        }
                        state::persist_draft(state).await?;
                        bridge.send(true)?;
                    }
                    UploadEvent::Error { message } => {
                        anyhow::bail!("Не удалось выбрать файл: {message}");
                    }
                    UploadEvent::Done => {
                        state.write().uploading = false;
                        upload = Upload::default();
                    }
                }
                Ok(())
            }
            .await;
            if result.is_err() {
                if expects_ack {
                    let _ = bridge.send(false);
                }
                state.write().uploading = false;
                upload = Upload::default();
            }
            state::report(state, result);
        }
        state.write().uploading = false;
    });
    rsx! {
        label {
            class: "file-button brand-button tone-create",
            title: "Добавить материал",
            "aria-label": "Добавить материал",
            icons::build_icon {
                name: if state.read().uploading { "hourglass_empty" } else { "add" },
            }
            input {
                id: "xopilot-android-materials",
                r#type: "file",
                multiple: true,
                disabled: state.read().busy || state.read().uploading,
            }
        }
    }
}
