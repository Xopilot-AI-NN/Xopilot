// Файл: Services/src/db/mod.rs
// Модуль локальной БД (SQLCipher-шифрование, WAL).
// Хранит настройки программы, чаты и сообщения.
//
// СХЕМА ВЕРСИОНИРУЕТСЯ через SQLite `PRAGMA user_version`.
// Каждое изменение архитектуры/новые настройки в будущем — это новая `if version < N { ... }`
// ветка в `migrate()`, никогда не переделывать уже выпущенные шаги — это гарантирует,
// что БД пользователя, созданная на старой версии приложения, безопасно доедет до актуальной,
// без потери данных.

use rusqlite::{params, Connection, OptionalExtension, Result};
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

/// Текущая версия схемы. Повышать при каждом изменении схемы и добавлять ветку в migrate().
const CURRENT_SCHEMA_VERSION: i32 = 1;

pub struct Database {
    conn: Connection,
}

impl Database {
    /// Открывает (или создаёт) зашифрованную БД по пути и применяет миграции до актуальной схемы.
    /// `key` — ключ шифрования (генерируется из пароля пользователя через argon2 на стороне модуля защиты — сюда приходит уже готовый хеш).
    pub fn open<P: AsRef<Path>>(path: P, key: &str) -> Result<Self> {
        let conn = Connection::open(path)?;

        // SQLCipher-ключ должен быть установлен первым запросом, до любых других операций
        conn.pragma_update(None, "key", key)?;

        // WAL — чтение не блокируется записью (важно при среднем потоке сообщений + UI читает историю одновременно)
        conn.pragma_update(None, "journal_mode", "WAL")?;
        conn.pragma_update(None, "foreign_keys", true)?;

        let db = Database { conn };
        db.migrate()?;
        Ok(db)
    }

    /// Применяет последовательно все недостающие миграции в одной транзакции,
    /// чтобы сбой посередине не оставил БД в половинчатом состоянии.
    fn migrate(&self) -> Result<()> {
        let version: i32 = self
            .conn
            .query_row("PRAGMA user_version", [], |row| row.get(0))?;

        if version >= CURRENT_SCHEMA_VERSION {
            return Ok(());
        }

        self.conn.execute_batch("BEGIN;")?;

        let result = self.run_migrations(version);

        match result {
            Ok(()) => {
                self.conn.execute_batch("COMMIT;")?;
                self.conn
                    .pragma_update(None, "user_version", CURRENT_SCHEMA_VERSION)?;
                Ok(())
            }
            Err(e) => {
                // откат при любой ошибке посреди миграции — старая схема остаётся целой и рабочей
                let _ = self.conn.execute_batch("ROLLBACK;");
                Err(e)
            }
        }
    }

    /// Последовательные шаги миграции. Каждый `if version < N` — отдельная версия схемы,
    /// выполняется ровно один раз для каждой БД. Старые ветки никогда не редактируются задним числом —
    /// только добавляются новые.
    fn run_migrations(&self, from_version: i32) -> Result<()> {
        if from_version < 1 {
            self.conn.execute_batch(
                "
                CREATE TABLE IF NOT EXISTS settings (
                    key         TEXT PRIMARY KEY,
                    value       TEXT NOT NULL,
                    updated_at  INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chats (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title       TEXT,
                    created_at  INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id     INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                    role        TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    created_at  INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
                ",
            )?;
        }

        // Пример будущего шага, когда потребуется новая архитектура/настройки:
        // if from_version < 2 {
        //     self.conn.execute_batch("ALTER TABLE ... ; CREATE TABLE ...;")?;
        // }

        let _ = from_version; // гасится когда появится хотя бы одна ветка выше

        Ok(())
    }

    // ---------- settings (key-value, updated_at для будущей cloud-синхронизации) ----------

    pub fn set_setting(&self, key: &str, value: &str) -> Result<()> {
        self.conn.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?1, ?2, ?3)
             ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            params![key, value, now()],
        )?;
        Ok(())
    }

    pub fn get_setting(&self, key: &str) -> Result<Option<String>> {
        self.conn
            .query_row(
                "SELECT value FROM settings WHERE key = ?1",
                params![key],
                |row| row.get(0),
            )
            .optional()
    }

    pub fn all_settings(&self) -> Result<Vec<(String, String, i64)>> {
        let mut stmt = self
            .conn
            .prepare("SELECT key, value, updated_at FROM settings")?;
        let rows = stmt.query_map([], |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)))?;
        rows.collect()
    }

    // ---------- chats / messages ----------

    pub fn create_chat(&self, title: &str) -> Result<i64> {
        self.conn.execute(
            "INSERT INTO chats (title, created_at) VALUES (?1, ?2)",
            params![title, now()],
        )?;
        Ok(self.conn.last_insert_rowid())
    }

    pub fn add_message(&self, chat_id: i64, role: &str, content: &str) -> Result<i64> {
        self.conn.execute(
            "INSERT INTO messages (chat_id, role, content, created_at) VALUES (?1, ?2, ?3, ?4)",
            params![chat_id, role, content, now()],
        )?;
        Ok(self.conn.last_insert_rowid())
    }

    /// Правит текст уже отправленного сообщения (редактирование в UI). Возвращает Ok(false), если сообщение с таким id не найдено.
    pub fn update_message(&self, message_id: i64, content: &str) -> Result<bool> {
        let affected = self.conn.execute(
            "UPDATE messages SET content = ?1 WHERE id = ?2",
            params![content, message_id],
        )?;
        Ok(affected > 0)
    }

    pub fn get_messages(&self, chat_id: i64) -> Result<Vec<(i64, String, String, i64)>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, role, content, created_at FROM messages WHERE chat_id = ?1 ORDER BY id ASC",
        )?;
        let rows = stmt.query_map(params![chat_id], |row| {
            Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?))
        })?;
        rows.collect()
    }

    pub fn list_chats(&self) -> Result<Vec<(i64, String, i64)>> {
        let mut stmt = self
            .conn
            .prepare("SELECT id, COALESCE(title, ''), created_at FROM chats ORDER BY created_at DESC")?;
        let rows = stmt.query_map([], |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)))?;
        rows.collect()
    }

    /// Текущая версия схемы этой ОТКРЫТОЙ БД (полезно для диагностики/UI «O приложении»).
    pub fn schema_version(&self) -> Result<i32> {
        self.conn
            .query_row("PRAGMA user_version", [], |row| row.get(0))
    }
}

fn now() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs() as i64
}