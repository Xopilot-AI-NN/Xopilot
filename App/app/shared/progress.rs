// Описание: Общая полоса прогресса без системных цветов и ложных 100% при неизвестном размере.
use dioxus::prelude::*;

#[component]
/// Известная доля меняет только transform; неизвестный объём показывает движущийся сегмент.
pub fn build_progress_bar(value: Option<f64>, label: String) -> Element {
    let value = value
        .filter(|fraction| fraction.is_finite())
        .map(|fraction| fraction.clamp(0.0, 1.0));
    let style = value.map(|fraction| format!("transform: scaleX({fraction});"));
    rsx! {
        div {
            class: "download-progress progress-track",
            role: "progressbar",
            "aria-label": label,
            "aria-valuemin": "0",
            "aria-valuemax": "100",
            "aria-valuenow": value.map(|fraction| fraction * 100.0),
            span {
                class: if value.is_some() { "progress-fill" } else { "progress-fill indeterminate" },
                style,
            }
        }
    }
}

/// Показывает переданный объём и процент только при известном полном размере.
pub fn byte_progress(completed: u64, total: Option<u64>) -> String {
    match total.filter(|total| *total > 0) {
        Some(total) => format!(
            "{:.0}% · {} / {}",
            (completed as f64 / total as f64 * 100.0).min(100.0),
            bytes(completed),
            bytes(total),
        ),
        None => format!("{} · размер уточняется", bytes(completed)),
    }
}

/// Использует двоичные единицы, соответствующие реальному числу байтов файла.
fn bytes(value: u64) -> String {
    if value >= 1024 * 1024 * 1024 {
        format!("{:.2} ГиБ", value as f64 / 1073741824.0)
    } else {
        format!("{:.1} МиБ", value as f64 / 1048576.0)
    }
}
