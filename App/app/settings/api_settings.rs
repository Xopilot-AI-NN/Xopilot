// Файл: App/app/settings/api_settings.rs
// Описание: Gemini, OpenRouter и любой совместимый сервер, в том числе локальный.
use crate::{
    app::state::{self, AppState},
    services::{
        self,
        api_chat::{self, ApiConfig},
    },
};
use dioxus::prelude::*;

#[component]
pub fn build_api_settings() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let mut url = use_signal(String::new);
    let mut model = use_signal(String::new);
    let mut key = use_signal(String::new);
    let mut loaded = use_signal(|| false);
    let mut status = use_signal(String::new);
    use_future(move || async move {
        let result = async {
            let store = state::store(state)?;
            let config =
                services::runtime::blocking(move || api_chat::configuration(&store)).await?;
            url.set(config.url);
            model.set(config.model);
            key.set(config.key);
            loaded.set(true);
            Ok(())
        }
        .await;
        loaded.set(true);
        state::report(state, result);
    });
    let busy = state.read().busy;
    rsx! {
        section { class: "section",
            h2 { "Модель и API" }
            p { class: "notice", "Запросы идут напрямую выбранному провайдеру. API-ключ хранится в зашифрованной локальной базе." }
            div { class: "row",
                button { class: "button", disabled: busy, onclick: move |_| url.set("https://generativelanguage.googleapis.com/v1beta/openai".into()), "Google AI Studio" }
                button { class: "button", disabled: busy, onclick: move |_| url.set("https://openrouter.ai/api/v1".into()), "OpenRouter" }
                button { class: "button", disabled: busy, onclick: move |_| { url.set("http://127.0.0.1:8080/v1".into()); key.set(String::new()); }, "llama-server" }
                button { class: "button", disabled: busy, onclick: move |_| { url.set("http://127.0.0.1:11434/v1".into()); key.set(String::new()); }, "Ollama" }
            }
            label { class: "field", "Адрес API", input { value: "{url}", placeholder: "https://example.com/v1", disabled: busy, oninput: move |e| url.set(e.value()) } }
            label { class: "field", "Идентификатор модели", input { value: "{model}", placeholder: "Идентификатор из каталога провайдера", disabled: busy, oninput: move |e| model.set(e.value()) } }
            label { class: "field", "API-ключ", input { r#type: "password", autocomplete: "off", value: "{key}", disabled: busy, oninput: move |e| key.set(e.value()) } }
            button { class: "button primary", disabled: busy || !*loaded.read(), onclick: move |_| { spawn(async move {
                let result = async {
                    let store = state::store(state)?;
                    let config = ApiConfig { url: url.read().clone(), model: model.read().clone(), key: key.read().clone() };
                    let selected = config.model.clone();
                    services::runtime::blocking(move || api_chat::save_configuration(&store, &config)).await?;
                    state.write().model = selected;
                    status.set("Настройки модели сохранены".into());
                    Ok(())
                }.await;
                state::report(state, result);
            }); }, "Сохранить модель" }
            p { class: "notice", role: "status", "{status}" }
            p { class: "notice", "Локальный сервер запускается отдельно. Формат .litertlm и прежний Python-runtime в эту версию не входят." }
        }
    }
}
