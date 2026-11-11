// Описание: Настоящий цикл агент → HTTP → инструменты → подтверждение → результат.
use anyhow::Result;
use serde_json::{Value, json};
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    sync::mpsc,
};
use tokio_util::sync::CancellationToken;
use xopilot::services::{
    agent, api_chat::ApiConfig, db::Store, generation::Configuration, workspaces::Workspace,
};
async fn scenario(allow: bool) -> Result<()> {
    let project = tempfile::tempdir()?;
    std::fs::write(project.path().join("example.txt"), "old")?;
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await?;
    let address = listener.local_addr()?;
    let server = tokio::spawn(async move {
        for step in 0..3 {
            let (mut stream, _) = listener.accept().await?;
            let mut bytes = Vec::new();
            let mut buffer = [0; 1024];
            let body = loop {
                let count = stream.read(&mut buffer).await?;
                assert!(count > 0);
                bytes.extend_from_slice(&buffer[..count]);
                if let Some(start) = bytes.windows(4).position(|w| w == b"\r\n\r\n") {
                    let headers = String::from_utf8_lossy(&bytes[..start]);
                    let length: usize = headers
                        .lines()
                        .find_map(|line| {
                            line.to_lowercase()
                                .strip_prefix("content-length:")
                                .map(|v| v.trim().parse().unwrap())
                        })
                        .unwrap();
                    if bytes.len() >= start + 4 + length {
                        break serde_json::from_slice::<Value>(
                            &bytes[start + 4..start + 4 + length],
                        )?;
                    }
                }
            };
            if step == 1 {
                assert!(
                    body["messages"].as_array().unwrap().last().unwrap()["content"]
                        .as_str()
                        .unwrap()
                        .contains("old")
                );
            }
            if step == 2 {
                assert!(
                    body["messages"].as_array().unwrap().last().unwrap()["content"]
                        .as_str()
                        .unwrap()
                        .contains(if allow {
                            "\"saved\":true"
                        } else {
                            "не подтвердил"
                        })
                );
            }
            let answer = match step {
                0 => json!({"tool":"read_project_file","arguments":{"path":"example.txt"}}),
                1 => {
                    json!({"tool":"write_project_file","arguments":{"path":"example.txt","content":"new"}})
                }
                _ => json!({"final":if allow{"Файл изменён"}else{"Действие отклонено"}}),
            };
            let response =
                json!({"choices":[{"message":{"content":answer.to_string()}}]}).to_string();
            stream.write_all(format!("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{response}",response.len()).as_bytes()).await?;
        }
        Ok::<_, anyhow::Error>(())
    });
    let store = Store::new(advanced_xopilot::db::Database::open(
        ":memory:",
        &"a".repeat(64),
    )?);
    let chat = store.with(|db| Ok(db.create_chat("Агент")?))?;
    let (events, mut receiver) = mpsc::unbounded_channel();
    let file = project.path().join("example.txt");
    let approvals = tokio::spawn(async move {
        let mut count = 0;
        while let Some(event) = receiver.recv().await {
            if let agent::Event::Approval(approval) = event {
                count += 1;
                assert_eq!(std::fs::read_to_string(&file).unwrap(), "old");
                assert!(approval.details.contains("example.txt"));
                approval.answer(allow);
            }
        }
        count
    });
    let context = agent::ContextData {
        store,
        chat,
        workspace: Workspace {
            folder: project.path().to_string_lossy().into(),
            ..Default::default()
        },
        settings: agent::Settings {
            enabled: true,
            ..Default::default()
        },
        control: Default::default(),
        events,
    };
    let (updates, _) = mpsc::unbounded_channel();
    let reply = agent::run(
        Configuration::Api(ApiConfig {
            url: format!("http://{address}/v1"),
            model: "agent-test".into(),
            key: String::new(),
        }),
        vec![
            json!({"role":"system","content":"Помощник"}),
            json!({"role":"user","content":"Измени файл"}),
        ],
        CancellationToken::new(),
        updates,
        context,
    )
    .await?;
    assert_eq!(
        reply,
        if allow {
            "Файл изменён"
        } else {
            "Действие отклонено"
        }
    );
    assert_eq!(
        std::fs::read_to_string(project.path().join("example.txt"))?,
        if allow { "new" } else { "old" }
    );
    assert_eq!(approvals.await?, 1);
    server.await??;
    Ok(())
}
#[tokio::test]
async fn agent_waits_for_approval_before_writing() {
    scenario(true).await.unwrap();
}
#[tokio::test]
async fn rejected_action_does_not_modify_the_file() {
    scenario(false).await.unwrap();
}
#[tokio::test]
async fn command_is_cancelled_without_waiting_for_timeout() {
    let root = tempfile::tempdir().unwrap();
    let token = CancellationToken::new();
    let cancellation = token.clone();
    let path = root.path().to_owned();
    let task = tokio::spawn(async move {
        agent::command(
            path,
            vec![
                "sh".into(),
                "-c".into(),
                "printf started > started.txt; sleep 30".into(),
            ],
            token,
        )
        .await
    });
    for _ in 0..100 {
        if root.path().join("started.txt").exists() {
            break;
        }
        tokio::time::sleep(std::time::Duration::from_millis(10)).await;
    }
    assert!(root.path().join("started.txt").exists());
    cancellation.cancel();
    assert!(
        tokio::time::timeout(std::time::Duration::from_secs(2), task)
            .await
            .unwrap()
            .unwrap()
            .is_err()
    );
}

#[tokio::test]
async fn repeated_read_switches_to_summary_without_an_endless_tool_loop() {
    let root = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("a.txt"), "same").unwrap();
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let address = listener.local_addr().unwrap();
    let server = tokio::spawn(async move {
        for step in 0..3 {
            let (mut stream, _) = listener.accept().await.unwrap();
            let mut buffer = Vec::new();
            let mut chunk = [0; 2048];
            let body = loop {
                let n = stream.read(&mut chunk).await.unwrap();
                assert!(n > 0);
                buffer.extend_from_slice(&chunk[..n]);
                if let Some(start) = buffer.windows(4).position(|w| w == b"\r\n\r\n") {
                    let headers = String::from_utf8_lossy(&buffer[..start]);
                    let length: usize = headers
                        .lines()
                        .find_map(|line| {
                            line.to_lowercase()
                                .strip_prefix("content-length:")
                                .map(|n| n.trim().parse().unwrap())
                        })
                        .unwrap();
                    if buffer.len() >= start + 4 + length {
                        break serde_json::from_slice::<Value>(
                            &buffer[start + 4..start + 4 + length],
                        )
                        .unwrap();
                    }
                }
            };
            let content = if step < 2 {
                json!({"tool":"read_project_file","arguments":{"path":"a.txt"}}).to_string()
            } else {
                assert_eq!(body["messages"].as_array().unwrap().len(), 2);
                assert!(
                    body["messages"][0]["content"]
                        .as_str()
                        .unwrap()
                        .contains("Tools are disabled")
                );
                "Файл прочитан, изменений не вносил.".into()
            };
            let response = json!({"choices":[{"message":{"content":content}}]}).to_string();
            stream.write_all(format!("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{response}",response.len()).as_bytes()).await.unwrap();
        }
    });
    let store =
        Store::new(advanced_xopilot::db::Database::open(":memory:", &"a".repeat(64)).unwrap());
    let chat = store.with(|db| Ok(db.create_chat("Тест")?)).unwrap();
    let (events, _) = mpsc::unbounded_channel();
    let (updates, _) = mpsc::unbounded_channel();
    let context = agent::ContextData {
        store,
        chat,
        workspace: Workspace {
            folder: root.path().to_string_lossy().into(),
            ..Default::default()
        },
        settings: agent::Settings {
            enabled: true,
            ..Default::default()
        },
        control: Default::default(),
        events,
    };
    let reply = agent::run(
        Configuration::Api(ApiConfig {
            url: format!("http://{address}/v1"),
            model: "test".into(),
            key: String::new(),
        }),
        vec![
            json!({"role":"system","content":"Helper"}),
            json!({"role":"user","content":"Прочитай a.txt"}),
        ],
        CancellationToken::new(),
        updates,
        context,
    )
    .await
    .unwrap();
    assert!(reply.starts_with("Остановил повторяющиеся действия."));
    assert!(reply.contains("изменений не вносил"));
    server.await.unwrap();
}
