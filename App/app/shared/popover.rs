// Описание: Выпадающее меню следует за кнопкой и остаётся внутри экрана/клавиатуры.
use dioxus::prelude::*;
/// Размещает меню у кнопки в пределах экрана и обрабатывает клавиатуру.
#[component]
pub fn build_popover(
    id: String,
    anchor: String,
    onclose: EventHandler<()>,
    children: Element,
    #[props(default = "menu".to_string())] role: String,
) -> Element {
    let cleanup = id.clone();
    let focus_anchor = anchor.clone();
    use_effect(use_reactive((&id, &anchor), move |(id, anchor)| {
        let script = format!(
            "const menuId={};const anchorId={};{}",
            serde_json::to_string(&id).unwrap(),
            serde_json::to_string(&anchor).unwrap(),
            include_str!("popover.js")
        );
        document::eval(&script);
    }));
    use_drop(move || {
        document::eval(&format!(
            "window.__xopilotPopovers?.[{}]?.abort();",
            serde_json::to_string(&cleanup).unwrap()
        ));
    });
    rsx! {
        button {
            class: "floating-scrim",
            title: "Закрыть выпадающее меню",
            "aria-label": "Закрыть выпадающее меню",
            tabindex: -1,
            onclick: move |_| onclose.call(()),
        }
        div {
            id,
            class: "floating-menu",
            role,
            onkeydown: move |e| {
                if e.key() == Key::Escape {
                    e.stop_propagation();
                    e.prevent_default();
                    let anchor = serde_json::to_string(&focus_anchor).unwrap();
                    document::eval(
                        &format!(
                            "let anchor=document.getElementById({anchor});if(!anchor?.getClientRects().length)anchor=document.getElementById('chat-tools-mobile');(anchor?.matches('button')?anchor:anchor?.querySelector('button'))?.focus({{preventScroll:true}});",
                        ),
                    );
                    onclose.call(());
                } else if e.key() == Key::Tab {
                    onclose.call(());
                }
            },
            {children}
        }
    }
}
