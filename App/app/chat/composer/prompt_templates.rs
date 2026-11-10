// Описание: Личные шаблоны вставляются в редактор с сохранением введённого текста.
use crate::app::shared::icons;
use crate::{
    app::state::{self, AppState, Screen},
    services::{
        self,
        prompt_templates::{self, Template},
    },
};
use dioxus::prelude::*;

#[component]
pub fn build_templates() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let mut items = use_signal(Vec::<Template>::new);
    let mut title = use_signal(String::new);
    let mut creating = use_signal(|| false);
    let mut query = use_signal(String::new);
    let mut body = use_signal(String::new);
    let mut revision = use_signal(|| 0u64);
    let _load = use_resource(move || {
        let _revision = *revision.read();
        async move {
            let result = async {
                let store = state::store(state)?;
                items.set(
                    services::runtime::blocking(move || prompt_templates::list_templates(&store))
                        .await?,
                );
                Ok(())
            }
            .await;
            state::report(state, result);
        }
    });
    let needle = query.read().to_lowercase();
    let templates: Vec<_> = items
        .read()
        .iter()
        .filter(|t| (t.title.clone() + &t.body).to_lowercase().contains(&needle))
        .cloned()
        .collect();
    rsx! {
        div { class: "page", div { class: "page-content",
            h1 { "Шаблоны запросов" }
            p { class: "notice", "На этом устройстве · текст добавляется к черновику, отправка отдельно." }
            div { class: "dialog-toolbar",
                label { class: "outlined-search", icons::build_icon { name: "search" } input { placeholder: "Поиск шаблонов", value: "{query}", oninput: move |e| query.set(e.value()) } }
                button { class: "button", onclick: move |_| creating.set(true), icons::build_icon { name: "add" } "Создать" }
            }
            if *creating.read() { section { class: "section",
                label { class: "field", "Название", input { value: "{title}", maxlength: 80, oninput: move |e| title.set(e.value()) } }
                label { class: "field", "Текст шаблона", textarea { value: "{body}", oninput: move |e| body.set(e.value()) } }
                button { class: "button primary", onclick: move |_| { spawn(async move {
                    let result = async {
                        let store = state::store(state)?;
                        let title_value = title.read().clone(); let body_value = body.read().clone();
                        services::runtime::blocking(move || prompt_templates::save(&store, &title_value, &body_value)).await?;
                        title.set(String::new()); body.set(String::new()); creating.set(false); revision += 1;
                        Ok(())
                    }.await;
                    state::report(state, result);
                }); }, "Добавить шаблон" }
            }
            }
            if templates.is_empty() { p { class: "notice", "Сохраните часто используемые инструкции кнопкой «Создать»." } }
            div { class: "list", for item in templates {
                section { class: "section", key: "{item.id}",
                    h2 { "{item.title}" }
                    p { style: "white-space:pre-wrap", "{item.body}" }
                    div { class: "row",
                        button { class: "button", onclick: move |_| {
                            let mut value = state.write();
                            if !value.draft.text.is_empty() { value.draft.text.push_str("\n\n"); }
                            value.draft.text.push_str(&item.body);
                            value.screen = Screen::Chat;
                            value.dialog_history.clear();
                        }, "Вставить в сообщение" }
                        button { class: "button danger", onclick: move |_| {
                            let id = item.id.clone();
                            spawn(async move {
                                let result = async {
                                    let store = state::store(state)?;
                                    services::runtime::blocking(move || prompt_templates::delete(&store, &id)).await?;
                                    revision += 1; Ok(())
                                }.await;
                                state::report(state, result);
                            });
                        }, "Удалить" }
                    }
                }
            } }
        } }
    }
}
