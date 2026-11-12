// Описание: Материалы из истории текущего профиля, поиск по названию.
use crate::app::{
    shared::icons,
    state::{self, AppState},
};
use dioxus::prelude::*;

/// Ищет вложения текущего профиля по названиям.
#[component]
pub fn build_materials() -> Element {
    let state = use_context::<Signal<AppState>>();
    let mut materials =
        use_signal(Vec::<(String, String)>::new);
    let mut query = use_signal(String::new);
    use_future(move || async move {
        let result = async {
            let store = state::store(state)?;
            let items = crate::services::runtime::blocking(
                move || {
                    store.with(|db| {
                        let mut files = Vec::new();
                        for (id, _, _) in db.list_chats()? {
                            for message in
                                db.get_messages(id)?
                            {
                                files.extend(
                                    message.attachments,
                                );
                            }
                        }
                        files.sort();
                        files.dedup();
                        Ok(files)
                    })
                },
            )
            .await?;
            materials.set(items);
            Ok(())
        }
        .await;
        state::report(state, result);
    });
    let needle = query.read().to_lowercase();
    rsx! {
        label {
            class: "outlined-search",
            icons::build_icon {
                name: "search",
            }
            input {
                placeholder: "Поиск материалов",
                value: "{query}",
                oninput: move |e| query.set(e.value()),
            }
        }
        div {
            class: "catalog-list",
            for (name, path) in materials.read().iter().filter(|(name, _)| name.to_lowercase().contains(&needle)) {
                div {
                    class: "catalog-row",
                    icons::build_icon {
                        name: "description",
                    }
                    span {
                        class: "catalog-copy",
                        strong {
                            "{name}"
                        }
                        small {
                            "{path}"
                        }
                    }
                }
            }
        }
        if materials.read().is_empty() {
            p {
                class: "notice dialog-empty",
                "Здесь появятся ваши материалы. Прикрепите файл к сообщению."
            }
        }
    }
}
