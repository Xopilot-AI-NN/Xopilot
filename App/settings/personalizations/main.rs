// Описание: Настройки оформления, инструкций и моделей ИИ.
use crate::{
    app::{
        shared::icons,
        state::{self, AppState, Screen},
        theme::palette::THEMES,
    },
    services::{self, profile},
};
use dioxus::prelude::*;

#[component]
pub fn build_personalizations(#[props(default)] memory_only: bool) -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let mut name = use_signal(String::new);
    let mut memory = use_signal(String::new);
    let mut language = use_signal(|| "ru".to_owned());
    let mut status = use_signal(String::new);
    let mut loaded = use_signal(|| false);
    let mut dirty = use_signal(|| false);
    let mut backend = use_signal(|| "cpu".to_string());
    crate::app::shared::unsaved::use_unsaved(dirty);
    use_future(move || async move {
        let result = async {
            let store = state::store(state)?;
            let selected_backend = store.with(|db| {
                Ok(db
                    .get_setting("llm_backend")?
                    .unwrap_or_else(|| "cpu".into()))
            })?;
            backend.set(selected_backend);
            let (profile, personal, saved_language) = services::runtime::blocking(move || {
                let profile = profile::read(&store)?;
                let (personal, language) = store.with(|db| {
                    Ok((
                        db.get_setting("personal_instructions")?.unwrap_or_default(),
                        db.get_setting("response_language")?
                            .unwrap_or_else(|| "ru".into()),
                    ))
                })?;
                Ok((profile, personal, language))
            })
            .await?;
            name.set(profile["name"].as_str().unwrap_or("Пользователь").into());
            memory.set(personal);
            language.set(saved_language);
            loaded.set(true);
            Ok(())
        }
        .await;
        state::report(state, result);
    });
    let theme = state.read().theme.clone();
    rsx! {
        if memory_only {
            if memory_only {
                h2 { class: "section-title", "Личные инструкции" }
                p { class: "notice", "Сведения, которые ИИ использует в будущих разговорах" }
                label { class: "field", "Личные инструкции для модели", textarea { value: "{memory}", oninput: move |e| { memory.set(e.value()); dirty.set(true); } } }
            }
            button { class: "button primary", disabled: !*loaded.read(), onclick: move |_| { spawn(async move {
                let result = async {
                    let store = state::store(state)?;
                    let name = name.read().clone(); let instructions = memory.read().clone();
                    services::runtime::blocking(move || profile::update(&store, &name, &instructions)).await?;
                    dirty.set(false);
                    status.set("Профиль сохранён".into()); Ok(())
                }.await; state::report(state, result);
            }); }, "Сохранить профиль" }
        } else {
            h2 { class: "section-title", "Внешний вид" }
            div { class: "preference-row",
                div { class: "preference-heading", span { class: "preference-icon tone-navigate", icons::build_icon { name: "dark_mode_outlined" } }
                    span { class: "catalog-copy", strong { "Тема оформления" } small { "Семь палитр для чата и всех окон" } }
                }
                crate::app::shared::select::build_select { id:"theme-choice", label:"Тема оформления", value: theme, options:THEMES.iter().map(|(key,title)|(key.to_string(),title.to_string())).collect::<Vec<_>>(), onchange: move |theme:String| { state.write().theme = theme.clone();
                    spawn(async move { let result = async {
                        let store = state::store(state)?;
                        services::runtime::blocking(move || store.with(|db| { db.set_setting("theme", &theme)?; Ok(()) })).await?;
                        status.set("Тема применена".into()); Ok(())
                    }.await; state::report(state, result); });
                } }
            }
            div { class: "preference-row",
                div { class: "preference-heading", span { class: "preference-icon tone-navigate", icons::build_icon { name: "language" } }
                    span { class: "catalog-copy", strong { "Язык ответов ИИ" } small { "Предпочтительный язык обычного чата и Live" } }
                }
                crate::app::shared::select::build_select { id:"language-choice", label:"Язык ответов ИИ", value: language.read().clone(), options:vec![("ru".into(),"Русский".into()),("en".into(),"English".into())], onchange: move |value:String| { language.set(value.clone());
                    spawn(async move { let result = async {
                        let store = state::store(state)?;
                        services::runtime::blocking(move || store.with(|db| { db.set_setting("response_language", &value)?; Ok(()) })).await?;
                        status.set("Язык ответов сохранён".into()); Ok(())
                    }.await; state::report(state, result); });
                } }
            }
            h2 { class: "section-title", "ИИ и Live" }
            button { class: "settings-navigation-row", onclick: move |_| state::navigate(state, Screen::Memory),
                span { class: "preference-icon tone-navigate", icons::build_icon { name: "psychology_outlined" } }
                span { class: "catalog-copy", strong { "Память обо мне" } small { "Сохранённые сведения, предпочтения и управление памятью" } }
                icons::build_icon { name: "chevron_right" }
            }
            self::build_preference_card { icon: "memory", title: "Устройство вычислений", description: "CPU совместим с большинством устройств. GPU зависит от драйвера и модели.",
                crate::app::shared::select::build_select { id:"backend-choice", label:"Ускорение ИИ", value:backend.read().clone(), options:vec![("cpu".into(),"CPU".into()),("gpu".into(),"GPU".into())],disabled:state.read().busy,onchange:move|selected:String|{backend.set(selected.clone());spawn(async move{let result=async{let store=state::store(state)?;services::runtime::blocking(move||{services::litert::unload()?;store.with(|db|{db.set_setting("llm_backend",&selected)?;Ok(())})}).await}.await;state::report(state,result);});
                }}
            }
            self::build_preference_card { icon: "smart_toy_outlined", title: "Модель чата", description: "Основная модель для обычных сообщений.",
                button { class: "preference-select choice-trigger", onclick: move |_| state::navigate(state, Screen::Model),
                    span { if state.read().model.is_empty() { "Модель не выбрана" } else if state.read().model_local { "{state.read().model}" } else { "API · {state.read().model}" } }
                    icons::build_icon { name: "expand_more" }
                }
            }
            self::build_preference_card { icon: "graphic_eq", title: "Модель Live", description: "Модель для распознавания речи и генерации ответа в Live.",
                button { class: "preference-select choice-trigger", disabled:true, "Модели Live не установлены" }
            }
            self::build_preference_card { icon: "record_voice_over", title: "Голос Live", description: "Тембр, которым Xopilot озвучивает ответы.",
                button { class: "preference-select choice-trigger", disabled:true, "Сначала установите голос" }
            }
        }
        p { class: "notice", role: "status", "{status}" }
    }
}

#[component]
fn build_preference_card(
    icon: String,
    title: String,
    description: String,
    children: Element,
) -> Element {
    rsx! {
        section { class: "preference-card",
            div { class: "preference-heading", span { class: "preference-icon tone-ai", icons::build_icon { name: icon } }
                span { class: "catalog-copy", strong { "{title}" } small { "{description}" } }
            }
            {children}
        }
    }
}
