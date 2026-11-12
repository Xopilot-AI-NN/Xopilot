// Описание: Консервативный выбор ускорителя по свободной памяти с запасом для ОС и кеша.
use serde::{Deserialize, Serialize};
use std::sync::{Mutex, OnceLock};
#[derive(
    Clone, Default, PartialEq, Serialize, Deserialize,
)]
pub struct Status {
    pub backend: String,
    pub reason: String,
    pub loading: bool,
}
static STATUS: OnceLock<Mutex<Status>> = OnceLock::new();
/// Даёт интерфейсу фактическое устройство, а не только выбранную настройку «Авто».
pub fn status() -> Status {
    STATUS
        .get_or_init(Default::default)
        .lock()
        .map(|s| s.clone())
        .unwrap_or_default()
}
/// Публикует начало загрузки или результат перехода на CPU.
pub fn set(backend: &str, reason: &str, loading: bool) {
    if let Ok(mut s) =
        STATUS.get_or_init(Default::default).lock()
    {
        *s = Status {
            backend: backend.into(),
            reason: reason.into(),
            loading,
        };
    }
}
/// Оценивает запас: удвоенный файл весов плюс 2 ГиБ для промежуточных данных и ОС.
pub fn fits_gpu(
    model_bytes: u64,
    free_bytes: Option<u64>,
) -> bool {
    free_bytes.is_some_and(|free| {
        free >= model_bytes
            .saturating_mul(2)
            .saturating_add(2 * 1024 * 1024 * 1024)
    })
}
/// Разбирает MemAvailable в Linux/Android, не считая весь объём RAM свободным.
fn available_ram() -> Option<u64> {
    let text =
        std::fs::read_to_string("/proc/meminfo").ok()?;
    text.lines()
        .find(|l| l.starts_with("MemAvailable:"))?
        .split_whitespace()
        .nth(1)?
        .parse::<u64>()
        .ok()?
        .checked_mul(1024)
}
/// Читает счётчики AMD VRAM; неизвестная память не трактуется как достаточная.
fn drm_memory() -> Option<u64> {
    let mut values = Vec::new();
    for entry in
        std::fs::read_dir("/sys/class/drm").ok()?.flatten()
    {
        let device = entry.path().join("device");
        let total = std::fs::read_to_string(
            device.join("mem_info_vram_total"),
        )
        .ok()
        .and_then(|n| n.trim().parse::<u64>().ok());
        let used = std::fs::read_to_string(
            device.join("mem_info_vram_used"),
        )
        .ok()
        .and_then(|n| n.trim().parse::<u64>().ok());
        if let (Some(total), Some(used)) = (total, used)
            && total > 0
        {
            values.push(total.saturating_sub(used));
        }
    }
    values.into_iter().min()
}
/// Ограничивает ожидание драйвера NVIDIA двумя секундами и завершает зависший процесс.
async fn nvidia_memory() -> Option<u64> {
    let mut command =
        tokio::process::Command::new("nvidia-smi");
    command
        .args([
            "--query-gpu=memory.free",
            "--format=csv,noheader,nounits",
        ])
        .kill_on_drop(true);
    let output = tokio::time::timeout(
        std::time::Duration::from_secs(2),
        command.output(),
    )
    .await
    .ok()?
    .ok()?;
    if !output.status.success() {
        return None;
    }
    String::from_utf8(output.stdout)
        .ok()?
        .lines()
        .map(|line| {
            line.trim()
                .parse::<u64>()
                .ok()?
                .checked_mul(1024 * 1024)
        })
        .collect::<Option<Vec<_>>>()?
        .into_iter()
        .min()
}
/// На телефоне GPU разделяет RAM с системой; на ПК используем реальные счётчики VRAM.
pub async fn choose(
    model_bytes: u64,
) -> (&'static str, String) {
    let free = if cfg!(target_os = "android") {
        available_ram()
    } else {
        let drm = drm_memory();
        let nvidia = nvidia_memory().await;
        match (drm, nvidia) {
            (Some(a), Some(b)) => Some(a.min(b)),
            (a, b) => a.or(b),
        }
    };
    if fits_gpu(model_bytes, free) {
        (
            "gpu",
            "Достаточно свободной памяти GPU; проверяем ускоритель".into(),
        )
    } else {
        (
            "cpu",
            if free.is_some() {
                "GPU не хватает свободной памяти с запасом; выбран CPU"
            } else {
                "Свободная память GPU неизвестна; выбран CPU"
            }
            .into(),
        )
    }
}
#[cfg(test)]
mod tests {
    /// Решение зависит от свободного остатка и запаса, а не от общего размера карты.
    #[test]
    fn insufficient_or_unknown_gpu_memory_uses_cpu() {
        assert!(!super::fits_gpu(
            3 * 1024 * 1024 * 1024,
            None
        ));
        assert!(!super::fits_gpu(
            3 * 1024 * 1024 * 1024,
            Some(4 * 1024 * 1024 * 1024)
        ));
        assert!(super::fits_gpu(
            3 * 1024 * 1024 * 1024,
            Some(8 * 1024 * 1024 * 1024)
        ));
        assert!(!super::fits_gpu(
            u64::MAX,
            Some(8 * 1024 * 1024 * 1024)
        ));
    }
}
