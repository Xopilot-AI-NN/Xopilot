// Описание: Нажатие на аватар открывает системный выбор изображения.
use crate::{
    app::{
        shared::icons,
        state::{self, AppState},
    },
    services,
};
use dioxus::prelude::*;
/// Открывает системный выбор изображения и сохраняет нормализованный аватар.
#[component]
pub fn build_avatar(value: String, onchange: EventHandler<String>) -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let mut working = use_signal(|| false);
    use_drop(move || {
        if let Ok(mut value) = state.try_write() {
            value.uploading = false;
        }
    });
    use_future(move || async move {
        if !cfg!(target_os = "android") {
            return;
        }
        use services::mobile_documents::{Upload, UploadEvent};
        let script = services::mobile_documents::PICKER_SCRIPT
            .replace("xopilot-android-materials", "profile-avatar-file");
        let mut bridge = document::eval(&script);
        let mut upload = Upload::default();
        let mut store = None;
        while let Ok(event) = bridge.recv::<UploadEvent>().await {
            let ack = matches!(
                &event,
                UploadEvent::Start { .. } | UploadEvent::Chunk { .. } | UploadEvent::End
            );
            let result = async {
                match event {
                    UploadEvent::Start { name, size } => {
                        anyhow::ensure!(size <= 8 * 1024 * 1024, "Изображение больше 8 МиБ");
                        store = Some(state::store(state)?);
                        upload.start(name, size)?;
                        working.set(true);
                        state.write().uploading = true;
                        bridge.send(true)?;
                    }
                    UploadEvent::Chunk { data } => {
                        upload.chunk(&data)?;
                        bridge.send(true)?;
                    }
                    UploadEvent::End => {
                        let (_, bytes) = upload.finish()?;
                        let store = store
                            .clone()
                            .ok_or_else(|| anyhow::anyhow!("Профиль недоступен"))?;
                        let encoded = services::runtime::blocking(move || {
                            services::profile::avatar(&store, &bytes)
                        })
                        .await?;
                        onchange.call(encoded);
                        bridge.send(true)?;
                    }
                    UploadEvent::Done => {
                        working.set(false);
                        state.write().uploading = false;
                    }
                    UploadEvent::Error { message } => anyhow::bail!("{message}"),
                }
                Ok(())
            }
            .await;
            if result.is_err() {
                if ack {
                    let _ = bridge.send(false);
                }
                working.set(false);
                state.write().uploading = false;
                upload = Upload::default();
            }
            state::report(state, result);
        }
    });
    rsx! {
        label {
            class: "profile-avatar-action",
            title: "Изменить аватар",
            "aria-label": "Изменить аватар",
            if value.is_empty() {
                span {
                    class: "profile-avatar",
                    icons::build_icon {
                        name: "person",
                    }
                }
            } else {
                img {
                    class: "profile-avatar",
                    src: "data:image/png;base64,{value}",
                    alt: "Аватар пользователя",
                }
            }
            span {
                class: "avatar-edit",
                icons::build_icon {
                    name: if *working.read() { "hourglass_empty" } else { "edit" },
                }
            }
            input {
                id: "profile-avatar-file",
                r#type: "file",
                accept: "image/*",
                disabled: *working.read() || state.read().busy,
                onchange: move |event| {
                    if cfg!(target_os = "android") {
                        return;
                    }
                    let Some(file) = event.files().into_iter().next() else {
                        return;
                    };
                    let path = file.path();
                    working.set(true);
                    state.write().uploading = true;
                    spawn(async move {
                        let result = async {
                            let store = state::store(state)?;
                            let encoded = services::runtime::blocking(move || services::profile::avatar_file(
                                    &store,
                                    &path,
                                ))
                                .await?;
                            onchange.call(encoded);
                            Ok(())
                        }
                            .await;
                        working.set(false);
                        state.write().uploading = false;
                        state::report(state, result);
                    });
                },
            }
        }
    }
}
