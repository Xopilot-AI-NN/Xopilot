// Описание: Объявления модулей shared в общей структуре приложения.
pub mod activity_dock;
pub mod components;
pub mod dialog;
pub mod icons;
#[cfg(target_os = "android")]
pub mod mobile_viewport;
pub mod notification_lifetime;
pub mod popover;
pub mod progress;
pub mod select;
pub mod session_lifecycle;
pub mod static_assets;
pub mod unsaved;
