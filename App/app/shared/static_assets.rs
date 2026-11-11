// Описание: Шрифты и логотип встроены в бинарь: отдельный .exe или Linux-файл не теряет оформление.
// Обслуживаем их штатным локальным протоколом WebView, без сети, base64 в разметке и временных файлов.
// Версия в URL не даёт WebView оставить старый шрифт после обновления приложения.
#[cfg(feature = "desktop")]
use dioxus::desktop as native;
#[cfg(all(feature = "mobile", not(feature = "desktop")))]
use dioxus::mobile as native;
use dioxus::prelude::*;

pub const FONT: &str = concat!(
    "/xopilot-static/",
    env!("CARGO_PKG_VERSION"),
    "/GoogleSans-Regular.ttf"
);
pub const ICONS: &str = concat!(
    "/xopilot-static/",
    env!("CARGO_PKG_VERSION"),
    "/MaterialIcons-Regular.otf"
);
pub const ICON: &str = concat!("/xopilot-static/", env!("CARGO_PKG_VERSION"), "/icon.png");

/// Отдаёт только заранее известные встроенные файлы, без доступа к произвольным путям диска.
#[component]
pub fn build_static_assets() -> Element {
    #[cfg(any(feature = "desktop", feature = "mobile"))]
    native::use_asset_handler("xopilot-static", |request, responder| {
        use native::wry::http::Response;
        let (mime, bytes): (&str, &[u8]) = match request.uri().path() {
            FONT => (
                "font/ttf",
                include_bytes!("../../assets/fonts/GoogleSans-Regular.ttf"),
            ),
            ICONS => (
                "font/otf",
                include_bytes!("../../assets/fonts/material/MaterialIcons-Regular.otf"),
            ),
            ICON => ("image/png", include_bytes!("../../assets/icon.png")),
            _ => {
                responder.respond(
                    Response::builder()
                        .status(404)
                        .body(Vec::<u8>::new())
                        .unwrap(),
                );
                return;
            }
        };
        responder.respond(
            Response::builder()
                .header("Content-Type", mime)
                .header("Cache-Control", "public, max-age=31536000, immutable")
                .body(bytes.to_vec())
                .unwrap(),
        );
    });
    rsx! {}
}
