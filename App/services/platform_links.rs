// Описание: Открываем проверенные HTTPS/локальные ссылки в системном браузере.
use anyhow::{Result, ensure};
/// Открывает разрешённую HTTPS-ссылку системным браузером.
pub fn open(url: &str) -> Result<()> {
    let parsed = reqwest::Url::parse(url)?;
    ensure!(
        parsed.scheme() == "https"
            || (parsed.scheme() == "http"
                && matches!(parsed.host_str(), Some("127.0.0.1" | "localhost" | "[::1]"))),
        "Недопустимая ссылка"
    );
    #[cfg(target_os = "android")]
    {
        super::android::open_url(url)?;
    }
    #[cfg(target_os = "linux")]
    {
        std::process::Command::new("xdg-open").arg(url).spawn()?;
    }
    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("rundll32")
            .args(["url.dll,FileProtocolHandler", url])
            .spawn()?;
    }
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open").arg(url).spawn()?;
    }
    Ok(())
}
