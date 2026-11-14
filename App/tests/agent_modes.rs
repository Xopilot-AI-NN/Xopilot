// Проверяю настоящие HTTP-вызовы режимов, чтение инструментом и приём уточнений.
use anyhow::Result;
use serde_json::{Value, json};
use std::sync::{Arc, Mutex};
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    sync::mpsc,
};
use tokio_util::sync::CancellationToken;
use xopilot::services::{
    agent::{self, ContextData, Event, Settings},
    agent_modes::{self, Depth, Mode},
    api_chat::ApiConfig,
    db::Store,
    generation::Configuration,
};

/// Отдельный совместимый сервер отвечает исследователям и исполнителю независимо.
async fn server() -> Result<(
    Configuration,
    Arc<Mutex<Vec<Value>>>,
    tokio::task::JoinHandle<()>,
)> {
    let listener =
        tokio::net::TcpListener::bind("127.0.0.1:0")
            .await?;
    let url =
        format!("http://{}/v1", listener.local_addr()?);
    let records = Arc::new(Mutex::new(Vec::new()));
    let requests = records.clone();
    let task = tokio::spawn(async move {
        loop {
            let Ok((mut stream, _)) =
                listener.accept().await
            else {
                break;
            };
            let requests = requests.clone();
            tokio::spawn(async move {
                let mut bytes = Vec::new();
                let mut chunk = [0; 4096];
                let body = loop {
                    let n = stream
                        .read(&mut chunk)
                        .await
                        .unwrap();
                    if n == 0 {
                        return;
                    }
                    bytes.extend_from_slice(&chunk[..n]);
                    if let Some(start) = bytes
                        .windows(4)
                        .position(|w| w == b"\r\n\r\n")
                    {
                        let headers =
                            String::from_utf8_lossy(
                                &bytes[..start],
                            );
                        let size: usize = headers
                            .lines()
                            .find_map(|s| {
                                s.to_lowercase()
                                    .strip_prefix(
                                        "content-length:",
                                    )
                                    .map(|s| {
                                        s.trim()
                                            .parse()
                                            .unwrap()
                                    })
                            })
                            .unwrap();
                        if bytes.len() >= start + 4 + size {
                            break serde_json::from_slice::<
                                Value,
                            >(
                                &bytes[start + 4
                                    ..start + 4 + size],
                            )
                            .unwrap();
                        }
                    }
                };
                requests.lock().unwrap().push(body.clone());
                let system = body["messages"][0]["content"]
                    .as_str()
                    .unwrap();
                let content = if system.contains(
                    "Give a short public work plan",
                ) {
                    "Проверю данные и результат".to_owned()
                } else if system
                    .contains("research specialist")
                {
                    let read = body["messages"]
                        .as_array()
                        .unwrap()
                        .iter()
                        .any(|m| {
                            m["role"] == "assistant"
                                && m["content"]
                                    .as_str()
                                    .is_some_and(|s| {
                                        s.contains(
                                            "list_canvases",
                                        )
                                    })
                        });
                    if read {
                        json!({"final":"Проверенный вывод: список документов прочитан"}).to_string()
                    } else {
                        json!({"tool":"list_canvases","arguments":{}}).to_string()
                    }
                } else {
                    tokio::time::sleep(
                        std::time::Duration::from_millis(
                            90,
                        ),
                    )
                    .await;
                    let note = body["messages"]
                        .to_string()
                        .contains("Добавь проверку");
                    json!({"final":if note {"Уточнённый ответ"} else {"Итог задачи"}}).to_string()
                };
                let payload=json!({"choices":[{"message":{"content":content}}]}).to_string();
                let header = format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
                    payload.len()
                );
                let _ = stream
                    .write_all(header.as_bytes())
                    .await;
                let _ = stream
                    .write_all(payload.as_bytes())
                    .await;
            });
        }
    });
    Ok((
        Configuration::Api(ApiConfig {
            url,
            model: "modes-test".into(),
            key: String::new(),
        }),
        records,
        task,
    ))
}

/// Уровни включают реальное количество проходов, пять исследователей вызывают чтение.
#[tokio::test]
async fn modes_execute_plans_workers_and_coordinator()
-> Result<()> {
    for mode in
        [Mode::Precise, Mode::Multi, Mode::Reinforced]
    {
        let directory = tempfile::tempdir()?;
        let store = Store::new(
            advanced_xopilot::db::Database::open(
                directory.path().join("test.db"),
                "key",
            )?,
        );
        let chat =
            store.with(|db| Ok(db.create_chat("Тест")?))?;
        let (config, requests, server) = server().await?;
        let (events, mut traces) =
            mpsc::unbounded_channel();
        let (updates, _) = mpsc::unbounded_channel();
        let content = if mode == Mode::Multi {
            json!([{"type":"text","text":"Проверь список документов"},{"type":"image_url","image_url":{"url":"data:image/png;base64,ZmFrZQ=="}}])
        } else {
            json!("Проверь список документов")
        };
        let answer=agent_modes::run(config,vec![json!({"role":"system","content":"Системные инструкции"}),json!({"role":"user","content":content})],CancellationToken::new(),updates,ContextData {
            store,chat,workspace:Default::default(),settings:Settings{enabled:true,mode,depth:Depth::Light,..Default::default()},control:Default::default(),events,
        }).await?;
        assert_eq!(answer, "Итог задачи");
        let requests = requests.lock().unwrap();
        let workers = requests
            .iter()
            .filter(|r| {
                r["messages"][0]["content"]
                    .as_str()
                    .unwrap()
                    .contains("research specialist")
            })
            .count();
        assert_eq!(
            workers,
            match mode {
                Mode::Precise => 0,
                Mode::Reinforced => 20,
                _ => 10,
            }
        );
        let planning = requests
            .iter()
            .filter(|r| {
                r["messages"][0]["content"]
                    .as_str()
                    .unwrap()
                    .contains(
                        "Give a short public work plan",
                    )
            })
            .count();
        assert_eq!(
            planning,
            match mode {
                Mode::Precise => 1,
                Mode::Reinforced => 7,
                _ => 0,
            }
        );
        if mode == Mode::Multi {
            let workers = requests.iter().filter(|r| {
                r["messages"][0]["content"]
                    .as_str()
                    .unwrap()
                    .contains("research specialist")
            });
            assert!(workers.clone().all(|r| {
                r["messages"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .any(|m| {
                        m["content"].as_array().is_some_and(
                            |parts| {
                                parts.iter().any(|p| {
                                    p["type"] == "image_url"
                                })
                            },
                        )
                    })
            }));
        }
        let mut tools = 0;
        let mut completed = 0;
        while let Ok(event) = traces.try_recv() {
            if matches!(&event,Event::ToolStarted{id,..} if *id>=10000)
            {
                tools += 1;
            }
            if let Event::Deliberation { state, .. } = event
                && state == "completed"
            {
                completed += 1;
            }
        }
        assert!(
            completed
                >= if mode == Mode::Precise {
                    1
                } else {
                    5
                }
        );
        assert_eq!(
            tools,
            match mode {
                Mode::Precise => 0,
                Mode::Reinforced => 10,
                _ => 5,
            }
        );
        server.abort();
    }
    assert_eq!(
        [
            Depth::Light,
            Depth::Medium,
            Depth::High,
            Depth::Maximum
        ]
        .map(Depth::rounds),
        [1, 2, 3, 4]
    );
    Ok(())
}

/// Уточнение, пришедшее во время запроса, сохраняется и учитывается до финального ответа.
#[tokio::test]
async fn running_task_accepts_note_and_closes_inbox_after_completion()
-> Result<()> {
    let directory = tempfile::tempdir()?;
    let store =
        Store::new(advanced_xopilot::db::Database::open(
            directory.path().join("test.db"),
            "key",
        )?);
    let chat =
        store.with(|db| Ok(db.create_chat("Тест")?))?;
    let (config, requests, server) = server().await?;
    let control = agent::Control::default();
    let input = control.clone();
    let (events, mut receiver) = mpsc::unbounded_channel();
    let (updates, _) = mpsc::unbounded_channel();
    let saved = store.clone();
    let task = tokio::spawn(agent_modes::run(
        config,
        vec![
            json!({"role":"system","content":"Инструкции"}),
            json!({"role":"user","content":"Исходная просьба"}),
        ],
        CancellationToken::new(),
        updates,
        ContextData {
            store,
            chat,
            workspace: Default::default(),
            settings: Settings {
                enabled: true,
                ..Default::default()
            },
            control,
            events,
        },
    ));
    tokio::time::timeout(
        std::time::Duration::from_secs(5),
        async {
            while requests.lock().unwrap().is_empty() {
                tokio::time::sleep(
                    std::time::Duration::from_millis(5),
                )
                .await;
            }
        },
    )
    .await?;
    input.submit("Добавь проверку")?;
    assert_eq!(task.await??, "Уточнённый ответ");
    assert!(input.submit("Поздний запрос").is_err());
    assert!(
        saved
            .with(|db| Ok(db.get_messages(chat)?))?
            .iter()
            .any(|m| m.content == "Добавь проверку")
    );
    let mut applied = false;
    while let Ok(event) = receiver.try_recv() {
        if matches!(event, Event::NotesApplied { .. }) {
            applied = true;
        }
    }
    assert!(applied);
    server.abort();
    Ok(())
}

/// Исследователь не получает изменяющие инструменты и не может подставить неизвестное имя.
#[test]
fn research_permissions_are_read_only() {
    for name in [
        "write_project_file",
        "run_project_command",
        "git_project",
        "create_canvas",
        "update_canvas",
        "save_memory",
        "unknown",
    ] {
        assert!(!agent::read_only_tool(name));
    }
    assert!(agent::read_only_tool("read_project_file"));
    let control = agent::Control::default();
    for _ in 0..20 {
        control.submit("Уточнение").unwrap();
    }
    assert!(control.submit("Лишнее").is_err());
    assert_eq!(control.take_pending().len(), 20);
}

/// Выключенный агент не запускает исследования из прежних настроек другого чата.
#[tokio::test]
async fn disabled_agent_ignores_saved_team_mode()
-> Result<()> {
    let directory = tempfile::tempdir()?;
    let store =
        Store::new(advanced_xopilot::db::Database::open(
            directory.path().join("test.db"),
            "key",
        )?);
    let chat =
        store.with(|db| Ok(db.create_chat("Тест")?))?;
    let (config, requests, server) = server().await?;
    let (events, _) = mpsc::unbounded_channel();
    let (updates, _) = mpsc::unbounded_channel();
    agent_modes::run(config,vec![json!({"role":"system","content":"Обычный чат"}),json!({"role":"user","content":"Привет"})],CancellationToken::new(),updates,ContextData{store,chat,workspace:Default::default(),settings:Settings{enabled:false,mode:Mode::Reinforced,..Default::default()},control:Default::default(),events}).await?;
    assert_eq!(requests.lock().unwrap().len(), 1);
    server.abort();
    Ok(())
}

/// Новые предпочтения восстанавливаются из той же защищённой базы.
#[test]
fn advanced_preferences_survive_reload() -> Result<()> {
    let directory = tempfile::tempdir()?;
    let store =
        Store::new(advanced_xopilot::db::Database::open(
            directory.path().join("test.db"),
            "key",
        )?);
    let chat =
        store.with(|db| Ok(db.create_chat("Тест")?))?;
    let settings = Settings {
        enabled: true,
        mode: Mode::Reinforced,
        depth: Depth::Maximum,
        reasoning: true,
        ..Default::default()
    };
    agent::save_settings(&store, chat, &settings)?;
    let restored = agent::settings(&store, chat)?;
    assert_eq!(restored.mode, Mode::Reinforced);
    assert_eq!(restored.depth, Depth::Maximum);
    assert!(restored.reasoning);
    assert!(!restored.automatic);
    assert!(!restored.read_only);
    let control = agent::Control::default();
    control.submit("Ожидает шага")?;
    let lifetime = control.close_on_drop();
    drop(lifetime);
    assert!(control.submit("Слишком поздно").is_err());
    assert_eq!(control.take_pending(), ["Ожидает шага"]);
    Ok(())
}
