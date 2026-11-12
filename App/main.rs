#![cfg_attr(
    all(target_os = "windows", not(debug_assertions)),
    windows_subsystem = "windows"
)]
// Файл: App/main.rs
// Разработчик: DenBroLiik
// Описание: Точка входа Xopilot для Linux и Android.

#[cfg(not(any(feature = "desktop", feature = "mobile")))]
fn main() {
    eprintln!(
        "Для запуска: cargo run -p xopilot --features desktop"
    );
}

/// Настраивает платформенное окно и запускает Dioxus.
#[cfg(any(feature = "desktop", feature = "mobile"))]
fn main() {
    xopilot::flow_trace::begin("Запуск Xopilot");
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("warn,xopilot=info")),
        )
        .init();
    xopilot::flow_trace::step("Настроено логирование");

    #[cfg(target_os = "android")]
    xopilot::services::startup::preload();

    xopilot::flow_trace::step(
        "Запуск платформенного интерфейса Dioxus",
    );

    #[cfg(not(target_os = "android"))]
    dioxus::LaunchBuilder::desktop()
        .with_cfg(
            dioxus::desktop::Config::new()
                .with_menu(None)
                .with_window(
                dioxus::desktop::WindowBuilder::new()
                    .with_title("Xopilot")
                    .with_window_icon(
                        dioxus::desktop::icon_from_memory(
                            include_bytes!(
                                "assets/icon.png"
                            ),
                        )
                        .ok(),
                    )
                    .with_inner_size(
                        dioxus::desktop::LogicalSize::new(
                            1060.0, 760.0,
                        ),
                    )
                    .with_min_inner_size(
                        dioxus::desktop::LogicalSize::new(
                            380.0, 560.0,
                        ),
                    ),
            ),
        )
        .launch(xopilot::app::main::build_app_ui);

    #[cfg(target_os = "android")]
    dioxus::launch(xopilot::app::main::build_app_ui);

    xopilot::flow_trace::end("Завершение Xopilot");
}
