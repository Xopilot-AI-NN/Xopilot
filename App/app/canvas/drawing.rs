// Редактор штрихов Canvas. WebView рисует жест сразу, Rust сохраняет документ.
use crate::{
    app::state::{self, AppState},
    services,
};
use anyhow::{Context, Result, ensure};
use base64::{Engine, engine::general_purpose::STANDARD};
use dioxus::prelude::*;
use serde::Deserialize;
use serde_json::{Value, json};
use std::path::PathBuf;

#[derive(Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
enum DrawingEvent {
    Changed { strokes: Value, size: Value },
    Export { png: String },
    Error { message: String },
}

/// Проверяет PNG, полученный из WebView, перед публикацией файла.
fn export_png(data: &str) -> Result<PathBuf> {
    let data = data
        .strip_prefix("data:image/png;base64,")
        .context("WebView не вернул PNG")?;
    ensure!(
        data.len() <= 10 * 1024 * 1024,
        "Рисунок слишком большой"
    );
    let bytes = STANDARD.decode(data)?;
    ensure!(
        bytes.starts_with(b"\x89PNG\r\n\x1a\n"),
        "Неверный формат рисунка"
    );
    services::exports::save_canvas_png(&bytes)
}

/// Принимает завершённые штрихи и экспортирует именно текущий рисунок.
#[component]
pub(super) fn build_drawing(
    strokes: Option<Value>,
    size: Option<Value>,
    onchange: EventHandler<(Value, Value)>,
    mut status: Signal<String>,
) -> Element {
    let state = use_context::<Signal<AppState>>();
    rsx! {
        div {
            class: "drawing-editor",
            onmounted: move |_| {
                let initial = json!({"strokes": strokes, "size": size});
                spawn(async move {
                    let mut bridge = document::eval(include_str!("drawing.js"));
                    if let Err(error) = bridge.send(initial) {
                        state::report(state, Err(error.into()));
                        return;
                    }
                    while let Ok(event) = bridge.recv::<DrawingEvent>().await {
                        match event {
                            DrawingEvent::Changed { strokes, size } => onchange.call((strokes, size)),
                            DrawingEvent::Export { png } => {
                                spawn(async move {
                                    match services::runtime::blocking(move || export_png(&png)).await {
                                        Ok(path) => status.set(format!("Рисунок сохранён: {}", path.display())),
                                        Err(error) => state::report(state, Err(error)),
                                    }
                                });
                            }
                            DrawingEvent::Error { message } => status.set(message),
                        }
                    }
                });
            },
            div {
                class: "row drawing-tools",
                label {
                    "Цвет кисти"
                    input { "data-ink": "", r#type: "color", value: "#123b43" }
                }
                label {
                    "Толщина"
                    input { "data-width": "", r#type: "range", min: "1", max: "15", value: "3" }
                }
                button { class: "button", "data-undo": "", disabled: true, "Отменить штрих" }
                button { class: "button", "data-redo": "", disabled: true, "Вернуть штрих" }
                button { class: "button", "data-export": "", disabled: true, "Экспорт PNG" }
            }
            canvas { class: "drawing-surface", "aria-label": "Холст для рисования" }
        }
    }
}
