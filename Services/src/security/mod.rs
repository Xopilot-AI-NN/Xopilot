// Файл: Services/src/security/mod.rs
// Получение ключа шифрования БД без участия пользователя.
//
// Основной путь: OS-хранилище секретов — Windows Credential Manager / Linux Secret Service
// (GNOME Keyring, KWallet). Целостный аналог Android Keystore: приложение не видит
// пароль/PIN от входа в ОС — оно просто просит системное хранилище выдать секрет, и
// система делает это сама, так как юзер уже разблокирован в своей сессии.
//
// Фоллбэк: если хранилище ОС недоступно (голый Linux без DE/D-Bus) — ключ выводится
// из machine-id + локальной соли на диске. Слабее (копирование всей папки сохраняет доступ),
// но не даёт приложению упасть на машинах без keyring-демона.

use rand::TryRng;
use rand::rngs::SysRng;
use sha2::{Digest, Sha256};
use std::path::Path;

const SERVICE: &str = "Xopilot";
const USERNAME: &str = "db-encryption-key";
const KEY_LEN: usize = 32;

/// Возвращает ключ шифрования (hex-строка — формат, который ожидает PRAGMA key у SQLCipher).
/// Генерируется один раз при первом запуске, дальше всегда читается оттуда же.
/// `fallback_dir` — куда класть файл соли для фоллбэк-ветки (обычно — папка рядом с БД).
pub fn get_db_keys(fallback_dir: &Path, existing_database: bool) -> Result<Vec<String>, String> {
    resolve_db_keys(fallback_dir, existing_database, get_or_create_from_keyring)
}

fn resolve_db_keys(
    dir: &Path, existing_database: bool,
    keyring_key: impl FnOnce(bool) -> Result<String, keyring::Error>,
) -> Result<Vec<String>, String> {
    let salt_exists = dir.join(".xopilot_salt").exists();
    let mut keys = Vec::new();
    let mut salt_error = None;
    if salt_exists {
        match get_or_create_fallback_key(dir) {
            Ok(key) => keys.push(key),
            Err(error) => salt_error = Some(error),
        }
    }
    // A database opened with the fallback must keep using that key when the
    // system keyring becomes available. Try existing keys, never rotate them.
    if let Ok(key) = keyring_key(!existing_database && !salt_exists) {
        if !keys.contains(&key) { keys.push(key); }
    }
    if !keys.is_empty() { return Ok(keys); }
    if let Some(error) = salt_error { return Err(error); }
    if existing_database {
        return Err("Ключ истории недоступен. Разблокируйте системное хранилище ключей и перезапустите Xopilot. Файл истории не изменён.".into());
    }
    Ok(vec![get_or_create_fallback_key(dir)?])
}

fn get_or_create_from_keyring(allow_create: bool) -> Result<String, keyring::Error> {
    let entry = keyring::Entry::new(SERVICE, USERNAME)?;
    match entry.get_password() {
        Ok(existing) => Ok(existing),
        Err(keyring::Error::NoEntry) if allow_create => {
            let key = generate_hex_key();
            entry.set_password(&key)?;
            Ok(key)
        }
        Err(e) => Err(e),
    }
}

fn get_or_create_fallback_key(dir: &Path) -> Result<String, String> {
    let salt_path = dir.join(".xopilot_salt");
    let salt: Vec<u8> = match std::fs::read(&salt_path) {
        Ok(bytes) if bytes.len() == KEY_LEN => bytes,
        Ok(_) => return Err("Файл ключа истории повреждён. Восстановите его из резервной копии; новый ключ не создавался.".into()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            let mut salt = [0u8; KEY_LEN];
            SysRng
                .try_fill_bytes(&mut salt)
                .expect("OS randomness unavailable while creating DB key salt");
            std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
            let mut options = std::fs::OpenOptions::new();
            options.write(true).create_new(true);
            #[cfg(unix)] {
                use std::os::unix::fs::OpenOptionsExt;
                options.mode(0o600);
            }
            use std::io::Write;
            let mut file = options.open(&salt_path).map_err(|e| e.to_string())?;
            file.write_all(&salt).map_err(|e| e.to_string())?;
            file.sync_all().map_err(|e| e.to_string())?;
            salt.to_vec()
        },
        Err(error) => return Err(error.to_string()),
    };

    let mut hasher = Sha256::new();
    hasher.update(&salt);
    hasher.update(read_machine_id().as_bytes());
    Ok(hex::encode(hasher.finalize()))
}

#[cfg(target_os = "linux")]
fn read_machine_id() -> String {
    std::fs::read_to_string("/etc/machine-id")
        .or_else(|_| std::fs::read_to_string("/var/lib/dbus/machine-id"))
        .unwrap_or_else(|_| "xopilot-fallback-id".to_string())
        .trim()
        .to_string()
}

#[cfg(target_os = "windows")]
fn read_machine_id() -> String {
    use winreg::RegKey;
    use winreg::enums::HKEY_LOCAL_MACHINE;

    RegKey::predef(HKEY_LOCAL_MACHINE)
        .open_subkey("SOFTWARE\\Microsoft\\Cryptography")
        .and_then(|key| key.get_value::<String, _>("MachineGuid"))
        .unwrap_or_else(|_| "xopilot-fallback-id".to_string())
}

fn generate_hex_key() -> String {
    let mut key = [0u8; KEY_LEN];
    SysRng
        .try_fill_bytes(&mut key)
        .expect("OS randomness unavailable while creating DB encryption key");
    hex::encode(key)
}

#[cfg(test)]
mod tests {
    use super::*;

    struct TestDir(std::path::PathBuf);
    impl TestDir {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!("xopilot-key-test-{}", generate_hex_key()));
            std::fs::create_dir_all(&path).unwrap();
            Self(path)
        }
    }
    impl Drop for TestDir {
        fn drop(&mut self) { let _ = std::fs::remove_dir_all(&self.0); }
    }

    #[test]
    fn fallback_survives_keyring_becoming_available() {
        let dir = TestDir::new();
        let first = resolve_db_keys(&dir.0, false, |_| Err(keyring::Error::NoEntry)).unwrap();
        let salt = std::fs::read(dir.0.join(".xopilot_salt")).unwrap();
        let reopened = resolve_db_keys(&dir.0, true, |allow_create| {
            assert!(!allow_create);
            Ok("existing-system-key".into())
        }).unwrap();
        assert_eq!(reopened[0], first[0]);
        assert_eq!(reopened.len(), 2);
        assert_eq!(std::fs::read(dir.0.join(".xopilot_salt")).unwrap(), salt);
    }

    #[test]
    fn missing_key_never_creates_a_replacement_for_existing_history() {
        let dir = TestDir::new();
        assert!(resolve_db_keys(&dir.0, true, |allow_create| {
            assert!(!allow_create);
            Err(keyring::Error::NoEntry)
        }).is_err());
        assert!(!dir.0.join(".xopilot_salt").exists());
    }

    #[test]
    fn corrupt_salt_is_preserved_instead_of_replaced() {
        let dir = TestDir::new();
        let salt = dir.0.join(".xopilot_salt");
        std::fs::write(&salt, b"damaged").unwrap();
        assert!(resolve_db_keys(&dir.0, true, |_| Err(keyring::Error::NoEntry)).is_err());
        assert_eq!(std::fs::read(salt).unwrap(), b"damaged");
    }

    #[test]
    fn existing_keyring_key_remains_an_option_with_a_corrupt_salt() {
        let dir = TestDir::new();
        std::fs::write(dir.0.join(".xopilot_salt"), b"damaged").unwrap();
        assert_eq!(resolve_db_keys(&dir.0, true, |_| Ok("existing-key".into())).unwrap(), vec!["existing-key"]);
    }
}
