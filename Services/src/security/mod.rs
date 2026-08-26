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

use rand::rngs::OsRng;
use rand::RngCore;
use sha2::{Digest, Sha256};
use std::path::Path;

const SERVICE: &str = "Xopilot";
const USERNAME: &str = "db-encryption-key";
const KEY_LEN: usize = 32;

/// Возвращает ключ шифрования (hex-строка — формат, который ожидает PRAGMA key у SQLCipher).
/// Генерируется один раз при первом запуске, дальше всегда читается оттуда же.
/// `fallback_dir` — куда класть файл соли для фоллбэк-ветки (обычно — папка рядом с БД).
pub fn get_or_create_db_key(fallback_dir: &Path) -> String {
    match get_or_create_from_keyring() {
        Ok(key) => key,
        Err(_) => get_or_create_fallback_key(fallback_dir),
    }
}

fn get_or_create_from_keyring() -> Result<String, keyring::Error> {
    let entry = keyring::Entry::new(SERVICE, USERNAME)?;
    match entry.get_password() {
        Ok(existing) => Ok(existing),
        Err(keyring::Error::NoEntry) => {
            let key = generate_hex_key();
            entry.set_password(&key)?;
            Ok(key)
        }
        Err(e) => Err(e),
    }
}

fn get_or_create_fallback_key(dir: &Path) -> String {
    let salt_path = dir.join(".xopilot_salt");
    let salt: Vec<u8> = match std::fs::read(&salt_path) {
        Ok(bytes) if bytes.len() == KEY_LEN => bytes,
        _ => {
            let mut salt = [0u8; KEY_LEN];
            OsRng.fill_bytes(&mut salt);
            let _ = std::fs::create_dir_all(dir);
            let _ = std::fs::write(&salt_path, salt);
            salt.to_vec()
        }
    };

    let mut hasher = Sha256::new();
    hasher.update(&salt);
    hasher.update(read_machine_id().as_bytes());
    hex::encode(hasher.finalize())
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
    use winreg::enums::HKEY_LOCAL_MACHINE;
    use winreg::RegKey;

    RegKey::predef(HKEY_LOCAL_MACHINE)
        .open_subkey("SOFTWARE\\Microsoft\\Cryptography")
        .and_then(|key| key.get_value::<String, _>("MachineGuid"))
        .unwrap_or_else(|_| "xopilot-fallback-id".to_string())
}

fn generate_hex_key() -> String {
    let mut key = [0u8; KEY_LEN];
    OsRng.fill_bytes(&mut key);
    hex::encode(key)
}