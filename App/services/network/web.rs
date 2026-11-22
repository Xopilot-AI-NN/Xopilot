// Описание: Поиск DuckDuckGo и чтение общедоступных страниц для агента.
// HTML разбирается как данные. Скрипты, формы и команды сайта не выполняются.
use anyhow::{Context, Result, bail, ensure};
use futures_util::StreamExt;
use reqwest::Url;
use scraper::{Html, Selector};
use serde::Serialize;
use std::{net::IpAddr, time::Duration};
use tokio_util::sync::CancellationToken;

const MAX_BYTES: usize = 2 * 1024 * 1024;
const MAX_TEXT: usize = 16000;

#[derive(Debug, Serialize)]
pub struct SearchResult {
    pub title: String,
    pub url: String,
    pub snippet: String,
}

#[derive(Debug, Serialize)]
pub struct Page {
    pub url: String,
    pub title: String,
    pub text: String,
    pub links: Vec<SearchResult>,
    pub truncated: bool,
}

/// Разрешает веб-адрес без учётных данных и сетевых протоколов других служб.
fn address(value: &str) -> Result<Url> {
    let mut url = Url::parse(value.trim())
        .context("Нужен полный адрес сайта")?;
    ensure!(
        matches!(url.scheme(), "http" | "https")
            && url.host_str().is_some(),
        "Разрешены адреса HTTP и HTTPS"
    );
    ensure!(
        url.username().is_empty()
            && url.password().is_none(),
        "Адрес сайта не должен содержать пароль"
    );
    url.set_fragment(None);
    Ok(url)
}

/// Веб-инструмент обращается к публичным сайтам. Локальные службы устройства
/// и служебные адреса не должны открываться по ссылке из недоверенной страницы.
fn public_ip(ip: IpAddr) -> bool {
    match ip {
        IpAddr::V4(ip) => {
            let [a, b, c, _] = ip.octets();
            !ip.is_private()
                && !ip.is_loopback()
                && !ip.is_link_local()
                && !ip.is_broadcast()
                && !ip.is_documentation()
                && a != 0
                && a < 224
                && !(a == 100 && (64..=127).contains(&b))
                && !(a == 198 && (b == 18 || b == 19))
                && !(a == 192 && b == 0 && c == 0)
        }
        IpAddr::V6(ip) => {
            if let Some(ip) = ip.to_ipv4_mapped() {
                return public_ip(ip.into());
            }
            let first = ip.segments()[0];
            (0x2000..0x4000).contains(&first)
                && !(first == 0x2001
                    && ip.segments()[1] < 0x200)
                && !(first == 0x2001
                    && ip.segments()[1] == 0xdb8)
        }
    }
}

/// Проверяет адрес на каждом перенаправлении и закрепляет проверенный DNS-ответ.
/// Ограничение размера действует и при передаче без Content-Length.
async fn fetch(
    value: &str,
    token: &CancellationToken,
) -> Result<(Url, String)> {
    let mut url = address(value)?;
    for _ in 0..6 {
        let host = url
            .host_str()
            .context("У адреса нет хоста")?
            .trim_matches(['[', ']']);
        let port = url
            .port_or_known_default()
            .context("Неизвестный порт")?;
        let addresses: Vec<_> = match host.parse::<IpAddr>()
        {
            Ok(ip) => {
                vec![std::net::SocketAddr::new(ip, port)]
            }
            Err(_) => tokio::net::lookup_host((host, port))
                .await?
                .collect(),
        };
        ensure!(
            !addresses.is_empty()
                && addresses
                    .iter()
                    .all(|address| public_ip(address.ip())),
            "Сайт должен иметь публичный интернет-адрес"
        );
        let client = super::http_client::builder()?
            .no_proxy()
            .redirect(reqwest::redirect::Policy::none())
            .resolve_to_addrs(host, &addresses)
            .timeout(Duration::from_secs(20))
            .user_agent("Xopilot/2.0.13 (web reader)")
            .build()?;
        let response =
            client.get(url.clone()).send().await?;
        if response.status().is_redirection() {
            let location = response
                .headers()
                .get(reqwest::header::LOCATION)
                .context(
                    "Сайт не указал адрес перенаправления",
                )?
                .to_str()?;
            url = address(url.join(location)?.as_str())?;
            continue;
        }
        ensure!(
            response.status().is_success(),
            "Сайт ответил HTTP {}",
            response.status()
        );
        let content_type = response
            .headers()
            .get(reqwest::header::CONTENT_TYPE)
            .and_then(|value| value.to_str().ok())
            .unwrap_or("")
            .to_owned();
        ensure!(
            content_type.is_empty()
                || content_type.starts_with("text/")
                || content_type.contains("xhtml"),
            "Для этого адреса нужен просмотр HTML или текста"
        );
        ensure!(
            response.content_length().unwrap_or(0)
                <= MAX_BYTES as u64,
            "Страница больше 2 МиБ"
        );
        let mut bytes = Vec::new();
        let mut stream = response.bytes_stream();
        while let Some(chunk) = stream.next().await {
            let chunk = chunk?;
            ensure!(
                bytes.len() + chunk.len() <= MAX_BYTES,
                "Страница больше 2 МиБ"
            );
            bytes.extend_from_slice(&chunk);
        }
        ensure!(!token.is_cancelled(), "Запрос отменён");
        return Ok((
            url,
            decode_html(&bytes, &content_type),
        ));
    }
    bail!("Слишком много перенаправлений")
}

/// Учитывает BOM, HTTP charset и meta charset для старых страниц, включая
/// Windows-1251. Размер исходного ответа уже проверен перед декодированием.
fn decode_html(bytes: &[u8], content_type: &str) -> String {
    let charset = |value: &str| {
        value.split(';').find_map(|part| {
            let (key, value) =
                part.trim().split_once('=')?;
            key.eq_ignore_ascii_case("charset").then(|| {
                value
                    .trim()
                    .trim_matches(['\"', '\''])
                    .to_owned()
            })
        })
    };
    let header = charset(content_type);
    let head = String::from_utf8_lossy(
        &bytes[..bytes.len().min(8192)],
    );
    let document = Html::parse_document(&head);
    let selector =
        Selector::parse("meta[charset], meta[http-equiv]")
            .unwrap();
    let meta =
        document.select(&selector).find_map(|element| {
            element
                .attr("charset")
                .map(str::to_owned)
                .or_else(|| {
                    charset(element.attr("content")?)
                })
        });
    let encoding = encoding_rs::Encoding::for_bom(bytes)
        .map(|(encoding, _)| encoding)
        .or_else(|| {
            header.or(meta).and_then(|label| {
                encoding_rs::Encoding::for_label(
                    label.as_bytes(),
                )
            })
        })
        .unwrap_or(encoding_rs::UTF_8);
    encoding.decode(bytes).0.into_owned()
}

/// Сводит пробелы и ограничивает текст по символам, сохраняя корректный UTF-8.
fn compact(text: &str, limit: usize) -> String {
    text.split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .chars()
        .take(limit)
        .collect()
}

/// Разворачивает ссылки DuckDuckGo, сохраняя прямой адрес источника.
fn result_url(base: &Url, href: &str) -> Option<String> {
    let url = base.join(href).ok()?;
    let destination =
        if url.host_str().is_some_and(|host| {
            host == "duckduckgo.com"
                || host.ends_with(".duckduckgo.com")
        }) && url.path().starts_with("/l/")
        {
            url.query_pairs()
                .find(|(key, _)| key == "uddg")?
                .1
                .into_owned()
        } else {
            url.to_string()
        };
    address(&destination).ok().map(|url| url.to_string())
}

/// Читает выдачу без рекламных блоков и HTML-разметки. Защита поисковика
/// отображается ошибкой, чтобы модель не принимала её за найденный ответ.
pub fn parse_search(
    html: &str,
) -> Result<Vec<SearchResult>> {
    ensure!(
        !html.contains("anomaly.js")
            && !html.contains("challenge-form"),
        "DuckDuckGo запросил проверку. Повторите поиск позже"
    );
    let document = Html::parse_document(html);
    let blocks = Selector::parse(".result").unwrap();
    let title = Selector::parse(".result__a").unwrap();
    let snippet =
        Selector::parse(".result__snippet").unwrap();
    let base =
        Url::parse("https://html.duckduckgo.com/html/")
            .unwrap();
    let mut results = Vec::new();
    for block in document.select(&blocks) {
        if block
            .value()
            .classes()
            .any(|class| class == "result--ad")
        {
            continue;
        }
        let Some(link) = block.select(&title).next() else {
            continue;
        };
        let Some(url) = link
            .attr("href")
            .and_then(|href| result_url(&base, href))
        else {
            continue;
        };
        if results
            .iter()
            .any(|result: &SearchResult| result.url == url)
        {
            continue;
        }
        results.push(SearchResult {
            title: compact(
                &link.text().collect::<String>(),
                250,
            ),
            url,
            snippet: block
                .select(&snippet)
                .next()
                .map(|element| {
                    compact(
                        &element.text().collect::<String>(),
                        1000,
                    )
                })
                .unwrap_or_default(),
        });
        if results.len() == 6 {
            break;
        }
    }
    ensure!(
        !results.is_empty()
            || html.contains("result--no-result")
            || html.contains("no-results"),
        "Не удалось распознать выдачу DuckDuckGo"
    );
    Ok(results)
}

/// Возвращает текст основного содержимого и ссылки, удаляя исполняемые узлы.
pub fn parse_page(url: &str, html: &str) -> Result<Page> {
    let base = address(url)?;
    let document = Html::parse_document(html);
    let selector =
        Selector::parse("main, article").unwrap();
    let body = Selector::parse("body").unwrap();
    let root = document
        .select(&selector)
        .next()
        .or_else(|| document.select(&body).next())
        .context("На странице нет текста")?;
    let mut text = String::new();
    for node in root.descendants() {
        let Some(value) = node.value().as_text() else {
            continue;
        };
        if node
            .ancestors()
            .filter_map(scraper::ElementRef::wrap)
            .any(|element| {
                matches!(
                    element.value().name(),
                    "script"
                        | "style"
                        | "noscript"
                        | "template"
                        | "svg"
                        | "nav"
                        | "footer"
                        | "header"
                )
            })
        {
            continue;
        }
        text.push_str(value);
        text.push(' ');
    }
    let text = text
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ");
    let title = Selector::parse("title").unwrap();
    let links = Selector::parse("a[href]").unwrap();
    let links = root
        .select(&links)
        .filter_map(|link| {
            let title = compact(
                &link.text().collect::<String>(),
                200,
            );
            if title.is_empty() {
                return None;
            }
            Some(SearchResult {
                title,
                url: result_url(&base, link.attr("href")?)?,
                snippet: String::new(),
            })
        })
        .take(20)
        .collect();
    Ok(Page {
        url: base.into(),
        title: document
            .select(&title)
            .next()
            .map(|element| {
                compact(
                    &element.text().collect::<String>(),
                    250,
                )
            })
            .unwrap_or_default(),
        truncated: text.chars().count() > MAX_TEXT,
        text: text.chars().take(MAX_TEXT).collect(),
        links,
    })
}

/// Выполняет сетевой поиск с отменой всего запроса, включая DNS и чтение тела.
pub async fn search(
    query: &str,
    token: &CancellationToken,
) -> Result<Vec<SearchResult>> {
    ensure!(
        !query.trim().is_empty()
            && query.chars().count() <= 500,
        "Введите поисковый запрос до 500 символов"
    );
    let mut url =
        Url::parse("https://html.duckduckgo.com/html/")?;
    url.query_pairs_mut().append_pair("q", query.trim());
    tokio::select! {
        _ = token.cancelled() => bail!("Поиск отменён"),
        result = tokio::time::timeout(Duration::from_secs(30), fetch(url.as_str(), token)) => {
            let (_, html) = result.context("Истекло время поиска")??;
            parse_search(&html)
        }
    }
}

/// Загружает сайт для анализа агентом. Результат содержит адрес для цитирования.
pub async fn read(
    url: &str,
    token: &CancellationToken,
) -> Result<Page> {
    tokio::select! {
        _ = token.cancelled() => bail!("Чтение сайта отменено"),
        result = tokio::time::timeout(Duration::from_secs(30), fetch(url, token)) => {
            let (url, html) = result.context("Истекло время чтения сайта")??;
            parse_page(url.as_str(), &html)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn honors_legacy_charset_headers_and_meta() {
        let html = "<meta charset=windows-1251><main>Привет, Денис</main>";
        let (bytes, _, _) =
            encoding_rs::WINDOWS_1251.encode(html);
        assert_eq!(decode_html(&bytes, "text/html"), html);
        assert_eq!(
            decode_html(
                &bytes,
                "text/html; charset=windows-1251"
            ),
            html
        );
    }
}
