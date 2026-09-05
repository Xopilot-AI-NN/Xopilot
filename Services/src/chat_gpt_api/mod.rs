use async_openai::{Client, config::OpenAIConfig};

// Create a OpenAI client with api key from env var OPENAI_API_KEY and default base url.
let client = Client::new();

// Above is shortcut for
let config = OpenAIConfig::default();
let client = Client::with_config(config);

// OR use API key from different source and a non default organization
let api_key = "sk-..."; // This secret could be from a file, or environment variable.
let config = OpenAIConfig::new()
    .with_api_key(api_key)
    .with_org_id("the-continental");

let client = Client::with_config(config);

// Use custom reqwest client
let http_client = reqwest::ClientBuilder::new().user_agent("async-openai").build().unwrap();
let client = Client::new().with_http_client(http_client);