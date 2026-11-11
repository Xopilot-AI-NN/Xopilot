// Описание: Неизвестный размер не выдаётся за 100%; известный прогресс доступен для screen reader.
use dioxus::prelude::*;
use xopilot::app::shared::progress;

/// Сопоставляет определённую и неопределённую полосы в одном статическом рендере.
fn fixture() -> Element {
    rsx! {
        progress::build_progress_bar {
            value: Some(0.5),
            label: "Известный размер",
        }
        progress::build_progress_bar {
            value: None,
            label: "Неизвестный размер",
        }
    }
}

/// В неопределённом состоянии нет aria-valuenow и выдуманного процента.
#[test]
fn progress_reports_only_known_amounts() {
    let mut dom = VirtualDom::new(fixture);
    dom.rebuild_in_place();
    let html = dioxus_ssr::render(&dom);
    assert_eq!(html.matches("aria-valuenow=").count(), 1);
    assert!(html.contains("aria-valuenow=50"), "{html}");
    assert!(html.contains("scaleX(0.5)"));
    assert!(html.contains("indeterminate"));
    assert!(progress::byte_progress(1048576, Some(2097152)).contains("50%"));
    assert!(!progress::byte_progress(1048576, None).contains('%'));
}
