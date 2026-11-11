// Описание: Автономные аккаунты. Каждый пароль открывает отдельную SQLCipher, сеть не используется.
use super::{db::Store, paths};
use advanced_xopilot::db::Database;
use anyhow::{Context, Result, ensure};
use serde::{Deserialize, Serialize};
use std::{
    io::Write,
    path::{Path, PathBuf},
};
use zeroize::Zeroizing;

#[derive(Clone, Default, Debug, Serialize, Deserialize, PartialEq)]
#[serde(default)]
pub struct Account {
    pub id: String,
    pub login: String,
    pub name: String,
    pub salt: String,
    pub database: String,
    pub created_at: f64,
}
pub struct Session {
    pub store: Store,
    pub root: Option<PathBuf>,
    pub account: Option<Account>,
}
#[derive(Clone, Default, Serialize, Deserialize)]
struct Index {
    accounts: Vec<Account>,
}
fn directory() -> Result<PathBuf> {
    Ok(paths::base_data_dir()?.join("accounts"))
}
fn root(id: &str) -> Result<PathBuf> {
    ensure!(uuid::Uuid::parse_str(id).is_ok(), "Неверный аккаунт");
    Ok(directory()?.join(id))
}
fn read_index() -> Result<Index> {
    let path = directory()?.join("index.json");
    if !path.exists() {
        return Ok(Index::default());
    }
    serde_json::from_slice(&std::fs::read(path)?)
        .context("Индекс аккаунтов повреждён; данные сохранены")
}
fn write_index(index: &Index) -> Result<()> {
    let directory = directory()?;
    std::fs::create_dir_all(&directory)?;
    let temp = directory.join(format!("index-{}.tmp", uuid::Uuid::new_v4()));
    let mut file = std::fs::OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(&temp)?;
    file.write_all(&serde_json::to_vec(index)?)?;
    file.sync_all()?;
    std::fs::rename(temp, directory.join("index.json"))?;
    Ok(())
}
fn lease() -> Result<std::fs::File> {
    let dir = directory()?;
    std::fs::create_dir_all(&dir)?;
    let file = std::fs::OpenOptions::new()
        .create(true)
        .truncate(false)
        .read(true)
        .write(true)
        .open(dir.join("index.lock"))?;
    fs2::FileExt::try_lock_exclusive(&file).context("Аккаунты изменяются в другом окне")?;
    Ok(file)
}
pub fn list() -> Result<Vec<Account>> {
    Ok(read_index()?.accounts)
}
fn session_lease(root: &Path) -> Result<std::fs::File> {
    let file = std::fs::OpenOptions::new()
        .create(true)
        .truncate(false)
        .read(true)
        .write(true)
        .open(root.join("session.lock"))?;
    fs2::FileExt::try_lock_exclusive(&file).context("Аккаунт уже открыт в другом окне")?;
    Ok(file)
}
fn key(password: &str, salt: &str) -> Result<Zeroizing<String>> {
    ensure!(
        password.chars().count() >= 8 && password.len() <= 1024,
        "Пароль должен содержать от 8 символов и до 1024 байт"
    );
    let salt = hex::decode(salt)?;
    ensure!(salt.len() == 16, "Неверная соль аккаунта");
    let mut key = Zeroizing::new([0u8; 32]);
    scrypt::scrypt(
        password.as_bytes(),
        &salt,
        &scrypt::Params::new(15, 8, 1, 32)?,
        key.as_mut(),
    )?;
    Ok(Zeroizing::new(hex::encode(*key)))
}
pub fn register(login: &str, name: &str, password: &str) -> Result<Session> {
    let login = login.trim().to_lowercase();
    let name = name.trim();
    ensure!(
        (3..=80).contains(&login.chars().count()) && !login.chars().any(char::is_control),
        "Логин: от 3 до 80 символов"
    );
    ensure!(
        !name.is_empty() && name.chars().count() <= 50 && !name.chars().any(char::is_control),
        "Имя: от 1 до 50 символов"
    );
    let _lease = lease()?;
    let mut index = read_index()?;
    ensure!(
        !index.accounts.iter().any(|a| a.login == login),
        "Этот логин уже существует на устройстве"
    );
    let account = Account {
        id: uuid::Uuid::new_v4().to_string(),
        login,
        name: name.into(),
        salt: hex::encode(uuid::Uuid::new_v4().as_bytes()),
        database: "xopilot.db".into(),
        created_at: super::canvases::now(),
    };
    let key = key(password, &account.salt)?;
    let root = root(&account.id)?;
    std::fs::create_dir_all(&root)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(&root, std::fs::Permissions::from_mode(0o700))?;
    }
    let result = (|| -> Result<Store> {
        let store = Store::new(Database::open(root.join(&account.database), &key)?)
            .with_lease(session_lease(&root)?);
        super::profile::update(&store, name, "")?;
        store.with(|db| {
            db.set_setting("local_account_id", &account.id)?;
            Ok(())
        })?;
        index.accounts.push(account.clone());
        write_index(&index)?;
        Ok(store)
    })();
    match result {
        Ok(store) => Ok(Session {
            store,
            root: Some(root),
            account: Some(account),
        }),
        Err(error) => {
            let _ = std::fs::remove_dir_all(root);
            Err(error)
        }
    }
}
fn account(id: &str) -> Result<Account> {
    read_index()?
        .accounts
        .into_iter()
        .find(|a| a.id == id)
        .context("Аккаунт больше не существует")
}
pub fn login(id: &str, password: &str) -> Result<Session> {
    let lease = session_lease(&root(id)?)?;
    let mut session = authenticate(id, password)?;
    session.store = session.store.with_lease(lease);
    Ok(session)
}
fn authenticate(id: &str, password: &str) -> Result<Session> {
    let account = account(id)?;
    let root = root(id)?;
    ensure!(
        Path::new(&account.database)
            .file_name()
            .and_then(|s| s.to_str())
            == Some(&account.database),
        "Неверный файл аккаунта"
    );
    let path = root.join(&account.database);
    ensure!(path.is_file(), "История аккаунта не найдена");
    let key = key(password, &account.salt)?;
    let db = Database::open(path, &key).map_err(|_| {
        anyhow::anyhow!("Неверный пароль или повреждённая история. Исходный файл сохранён")
    })?;
    Ok(Session {
        store: Store::new(db),
        root: Some(root),
        account: Some(account),
    })
}
pub fn guest() -> Result<Session> {
    Ok(Session {
        store: Store::open()?,
        root: None,
        account: None,
    })
}
pub fn delete(current: &Store, id: &str, password: &str) -> Result<()> {
    let _lease = lease()?;
    ensure!(
        self::current(current)?.as_ref().is_some_and(|a| a.id == id),
        "Удалять можно только открытый аккаунт"
    );
    let session = authenticate(id, password)?;
    drop(session);
    let mut index = read_index()?;
    index.accounts.retain(|a| a.id != id);
    // Сначала переименовываем папку. При сбое записи индекса восстанавливаем её.
    let original = root(id)?;
    let trash = directory()?.join(format!("deleted-{}", uuid::Uuid::new_v4()));
    std::fs::rename(&original, &trash)?;
    if let Err(error) = write_index(&index) {
        let _ = std::fs::rename(&trash, &original);
        return Err(error);
    }
    std::fs::remove_dir_all(trash)?;
    Ok(())
}
pub fn change_password(current: &Store, id: &str, old: &str, new: &str) -> Result<Session> {
    let _lease = lease()?;
    ensure!(
        self::current(current)?.as_ref().is_some_and(|a| a.id == id),
        "Сначала откройте этот аккаунт"
    );
    let original = authenticate(id, old)?;
    let old_file = original.account.as_ref().unwrap().database.clone();
    let mut account = original.account.clone().unwrap();
    account.salt = hex::encode(uuid::Uuid::new_v4().as_bytes());
    account.database = format!("history-{}.db", uuid::Uuid::new_v4());
    let key = key(new, &account.salt)?;
    let directory = original.root.clone().unwrap();
    let destination = directory.join(&account.database);
    current.with(|db| {
        db.export_encrypted(&destination, &key)?;
        Ok(())
    })?;
    let store = Store::new(Database::open(&destination, &key)?).retain_lease(current);
    let mut index = read_index()?;
    let entry = index
        .accounts
        .iter_mut()
        .find(|a| a.id == id)
        .context("Аккаунт удалён")?;
    *entry = account.clone();
    if let Err(error) = write_index(&index) {
        drop(store);
        let _ = std::fs::remove_file(destination);
        return Err(error);
    }
    drop(original);
    // Индекс уже указывает на новый снимок; старый пароль больше не оставляет копию истории.
    // На Unix открытые старые handle закроются при смене состояния окна.
    for suffix in ["", "-wal", "-shm"] {
        let _ = std::fs::remove_file(directory.join(format!("{old_file}{suffix}")));
    }
    Ok(Session {
        store,
        root: Some(directory),
        account: Some(account),
    })
}
pub fn current(store: &Store) -> Result<Option<Account>> {
    let id = store.with(|db| Ok(db.get_setting("local_account_id")?))?;
    id.map(|id| account(&id)).transpose()
}
#[derive(Clone, Default)]
pub struct Usage {
    pub chats: usize,
    pub messages: i64,
    pub bytes: u64,
    pub cached_cloud: bool,
}
pub fn usage(store: &Store, root: &Path) -> Result<Usage> {
    let (chats, messages, cached_cloud) = store.with(|db| {
        Ok((
            db.list_chats()?.len(),
            db.total_message_count()?,
            db.get_setting("cloud_account_v1")?.is_some(),
        ))
    })?;
    let mut bytes = 0u64;
    let mut pending = vec![root.to_path_buf()];
    let mut count = 0;
    while let Some(dir) = pending.pop() {
        if let Ok(entries) = std::fs::read_dir(dir) {
            for entry in entries.flatten() {
                if root == paths::base_data_dir()?.as_path()
                    && entry.path().parent() == Some(root)
                    && ["accounts", "models", "runtime"]
                        .contains(&entry.file_name().to_string_lossy().as_ref())
                {
                    continue;
                }
                count += 1;
                if count > 100_000 {
                    break;
                }
                let kind = entry.file_type()?;
                if kind.is_dir() {
                    pending.push(entry.path());
                } else if kind.is_file() {
                    bytes = bytes.saturating_add(entry.metadata()?.len());
                }
            }
        }
    }
    Ok(Usage {
        chats,
        messages,
        bytes,
        cached_cloud,
    })
}
