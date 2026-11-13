// Описание: Проверяем выдачу, содержимое сайтов и защиту от недоверенного HTML.
use tokio_util::sync::CancellationToken;
use xopilot::services::web;

#[test]
fn search_unwraps_links_removes_ads_and_deduplicates() {
    let results = web::parse_search(r#"
        <div class="result result--ad"><a class="result__a" href="https://ad.example">Ad</a></div>
        <div class="result"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fdoc%3Fa%3D1%26b%3D2">Rust &amp; docs</a><span class="result__snippet">A <b>useful</b> page</span></div>
        <div class="result"><a class="result__a" href="https://example.com/doc?a=1&amp;b=2">Duplicate</a></div>
        <div class="result"><a class="result__a" href="javascript:alert(1)">Invalid</a></div>
    "#).unwrap();
    assert_eq!(results.len(), 1);
    assert_eq!(results[0].title, "Rust & docs");
    assert_eq!(
        results[0].url,
        "https://example.com/doc?a=1&b=2"
    );
    assert_eq!(results[0].snippet, "A useful page");
    assert!(
        web::parse_search(
            "<form id='challenge-form'>captcha</form>"
        )
        .is_err()
    );
    assert!(
        web::parse_search("<html>unknown response</html>")
            .is_err()
    );
    assert!(
        web::parse_search(
            "<div class='no-results'>Nothing found</div>"
        )
        .unwrap()
        .is_empty()
    );
}

#[test]
fn site_reading_keeps_content_and_resolves_links() {
    let page = web::parse_page("https://example.com/guide/", r#"
        <title>Guide &amp; examples</title><nav>menu</nav>
        <main><h1>Привет</h1><p>Содержимое страницы</p>
        <script>secret script</script><style>secret style</style>
        <a href="../reference">Справка</a><a href="file:///etc/passwd">invalid</a></main>
        <footer>footer</footer>
    "#).unwrap();
    assert_eq!(page.title, "Guide & examples");
    assert_eq!(
        page.text,
        "Привет Содержимое страницы Справка invalid"
    );
    assert_eq!(page.links.len(), 1);
    assert_eq!(
        page.links[0].url,
        "https://example.com/reference"
    );
    assert!(!page.truncated);
    assert!(
        web::parse_page("file:///etc/passwd", "x").is_err()
    );
    let long =
        format!("<main>{}</main>", "т".repeat(18000));
    let page =
        web::parse_page("https://example.com/", &long)
            .unwrap();
    assert!(page.truncated);
    assert_eq!(page.text.chars().count(), 16000);
}

#[tokio::test]
async fn web_requests_respect_cancellation_and_block_local_services()
 {
    let token = CancellationToken::new();
    token.cancel();
    assert!(web::search("Rust", &token).await.is_err());
    assert!(
        web::read("https://example.com", &token)
            .await
            .is_err()
    );
    let token = CancellationToken::new();
    assert!(
        web::read("http://127.0.0.1", &token)
            .await
            .is_err()
    );
    assert!(
        web::read("http://[::1]", &token).await.is_err()
    );
    assert!(
        web::read("http://169.254.169.254", &token)
            .await
            .is_err()
    );
    assert!(web::search("", &token).await.is_err());
}

#[tokio::test]
#[ignore = "Обращается к настоящим сайтам, запускается отдельно при наличии интернета"]
async fn live_network_search_and_read() {
    let token = CancellationToken::new();
    let results = web::search(
        "Rust programming language official",
        &token,
    )
    .await
    .unwrap();
    assert!(!results.is_empty());
    println!("DuckDuckGo: {}", results[0].url);
    let page =
        web::read("https://www.rust-lang.org/", &token)
            .await
            .unwrap();
    assert!(page.text.to_lowercase().contains("rust"));
    println!(
        "Страница: {} · {} символов",
        page.url,
        page.text.chars().count()
    );
}

#[tokio::test]
#[ignore = "Нужны интернет и XOPILOT_TEST_MODEL с локальной Gemma"]
async fn local_agent_reads_a_site_without_workspace() {
    use serde_json::json;
    use tokio::sync::mpsc;
    use xopilot::services::{
        agent, db::Store, generation::Configuration,
        workspaces::Workspace,
    };
    let path = std::env::var_os("XOPILOT_TEST_MODEL")
        .expect("Укажите XOPILOT_TEST_MODEL");
    let store = Store::new(
        advanced_xopilot::db::Database::open(
            ":memory:",
            &"a".repeat(64),
        )
        .unwrap(),
    );
    let chat = store
        .with(|db| Ok(db.create_chat("Web smoke")?))
        .unwrap();
    let (events, mut receiver) = mpsc::unbounded_channel();
    let records = tokio::spawn(async move {
        let mut outputs = Vec::new();
        let mut tools = std::collections::HashMap::new();
        while let Some(event) = receiver.recv().await {
            match event {
                agent::Event::Approval(request) => {
                    request.answer(false)
                }
                agent::Event::ToolStarted {
                    id,
                    tool,
                    ..
                } => {
                    tools.insert(id, tool);
                }
                agent::Event::ToolFinished {
                    id,
                    output,
                    ..
                } => {
                    outputs.push((
                        tools
                            .remove(&id)
                            .unwrap_or_default(),
                        output,
                    ));
                }
                _ => {}
            }
        }
        outputs
    });
    let (updates, mut chunks) = mpsc::unbounded_channel();
    let drain = tokio::spawn(async move {
        while chunks.recv().await.is_some() {}
    });
    let result = tokio::time::timeout(std::time::Duration::from_secs(180), agent::run(
        Configuration::Local { path: path.into(), backend: "cpu".into() },
        vec![json!({"role":"user","content":"Use read_website to open https://www.rust-lang.org/ . In one sentence explain what Rust is and cite the website URL. Actually read it first. No workspace is attached or needed."})],
        CancellationToken::new(), updates,
        agent::ContextData { store, chat, workspace: Workspace::default(), settings: agent::Settings { enabled:true, ..Default::default() }, control:agent::Control::default(), events },
    )).await.unwrap().unwrap();
    drain.await.unwrap();
    let records = records.await.unwrap();
    println!("ANSWER {result}");
    println!("TOOLS {records:?}");
    assert!(
        records
            .iter()
            .any(|(tool, output)| tool == "read_website"
                && output["ok"] == true)
    );
    assert!(result.contains("rust-lang.org"));
}
