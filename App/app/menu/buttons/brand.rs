// Файл: App/app/menu/buttons/brand.rs
// Описание: Геометрия и роли тональных кнопок из Flet-версии.
use crate::app::shared::icons;
use dioxus::prelude::*;

#[component]
pub fn build_brand_button(
    icon: String,
    label: String,
    #[props(default = "navigate".into())] role: String,
    #[props(default = 40)] size: u16,
    #[props(default)] disabled: bool,
    onclick: EventHandler<MouseEvent>,
) -> Element {
    rsx! {
        button { class: "brand-button tone-{role}", style: "--button-size:{size}px",
            r#type: "button", title: "{label}", "aria-label": "{label}", disabled,
            onclick: move |event| onclick.call(event),
            icons::build_icon { name: icon }
        }
    }
}
