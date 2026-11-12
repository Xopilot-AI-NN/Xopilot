// Описание: Общие доверенные корни TLS для сетевых сервисов приложения.
use anyhow::Result;

/// Создаёт HTTPS-клиент с корнями Mozilla, как в прежнем reqwest/rustls.
/// В reqwest 0.13 проверка по умолчанию использует системный verifier. На Android
/// ему нужны дополнительные Java-классы, поэтому задаём корни явно в Rust.
pub fn builder() -> Result<reqwest::ClientBuilder> {
    let certificates = webpki_root_certs::TLS_SERVER_ROOT_CERTS
        .iter()
        .map(|certificate| reqwest::Certificate::from_der(certificate.as_ref()))
        .collect::<reqwest::Result<Vec<_>>>()?;
    Ok(reqwest::Client::builder().tls_certs_only(certificates))
}
