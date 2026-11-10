// Файл: App/app/chat/composer/prompt.rs
// Описание: Две строки, как в Flet: поле ввода и компактные инструменты.
use super::buttons::{add_material, send};
use crate::app::{
    menu::buttons::brand,
    shared::icons,
    state::{self, AppState, Screen},
};
use dioxus::prelude::*;

#[component]
pub fn build_prompt() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let draft = state.read().draft.clone();
    let model = state.read().model.clone();
    let busy = state.read().busy;
    let has_prompt = !draft.text.is_empty() || !draft.files.is_empty();
    rsx! {
        div { class: "composer-area",
            div { class: "composer",
                if !draft.files.is_empty() {
                    div { class: "files", for (index, (name, _)) in draft.files.into_iter().enumerate() {
                        button { class: "attachment", title: "Убрать вложение", disabled: busy,
                            onclick: move |_| { state.write().draft.files.remove(index); }, icons::build_icon { name: "description" } "{name}" icons::build_icon { name: "close" } }
                    } }
                }
                textarea { id: "chat-prompt", rows: 1, placeholder: "Напишите сообщение…", "aria-label": "Сообщение", value: "{draft.text}", disabled: busy,
                    oninput: move |event| {
                        state.write().draft.text = event.value();
                        document::eval("const field=document.getElementById('chat-prompt'); if(field){field.style.height='auto';field.style.height=Math.max(52,Math.min(field.scrollHeight,138))+'px';}");
                    },
                    onkeydown: move |event| {
                        if event.key() == Key::Enter && !event.modifiers().shift() && !event.is_composing() {
                            event.prevent_default();
                            spawn(async move { let result = state::send(state).await; state::report(state, result); });
                        }
                    }
                }
                div { class: "composer-tools",
                    if cfg!(target_os = "android") { add_material::build_android_material_button {} }
                    else { add_material::build_add_material_button {} }
                    button { class: "model-button tone-ai", title: "Выбор модели", "aria-label": "Выбор модели", onclick: move |_| state::navigate(state, Screen::Model),
                        span { class: "model-robot", icons::build_icon { name: "smart_toy_outlined" } }
                        span { class: "model-name", if model.is_empty() { span { class: "desktop-model-label", "Модель не выбрана" } span { class: "mobile-model-label", "Модель" } }
                            else { "API · {model}" }
                        }
                        icons::build_icon { name: "expand_more" }
                    }
                    button { class: "confirmation-button", title: "Подтверждение действий · Вручную", "aria-label": "Подтверждение действий · Вручную", onclick: move |_| state.write().notice = Some("Подтверждение действий агента ещё переносится. Сейчас доступны обычные ответы модели.".into()),
                        icons::build_icon { name: "fact_check_outlined" } span { "Вручную" }
                    }
                    span { class: "spacer" }
                    brand::build_brand_button { icon: "mic", label: "Диктовка", role: "ai", onclick: move |_| state.write().notice = Some("Диктовка ещё переносится в новую версию.".into()) }
                    if has_prompt || busy { send::build_send_button {} }
                    else { brand::build_brand_button { icon: "graphic_eq", label: "Live — голосовой разговор", role: "ai", onclick: move |_| state.write().notice = Some("Live ещё переносится в новую версию.".into()) } }
                }
            }
        }
    }
}
