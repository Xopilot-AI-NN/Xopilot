// Описание: Android Insets приходят из Rust, высота видимой области — из WebView.
use dioxus::prelude::*;

/// Связывает системные панели и visualViewport без изменения desktop-компоновки.
#[component]
pub fn build_mobile_viewport() -> Element {
    use_future(move || async move {
        let _ = document::eval(include_str!("mobile_viewport.js")).await;
        let mut previous = None;
        loop {
            if let Ok(Some(insets)) = crate::services::android::window_insets()
                && previous != Some(insets)
            {
                previous = Some(insets);
                if let Ok(json) = serde_json::to_string(&insets) {
                    document::eval(&format!("window.xopilotSetInsets?.({json});"));
                }
            }
            crate::services::runtime::background(async {
                tokio::time::sleep(std::time::Duration::from_millis(200)).await;
            })
            .await;
        }
    });
    rsx! {}
}
