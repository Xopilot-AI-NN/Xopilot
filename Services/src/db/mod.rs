// Файл: Services/src/db/mod.rs
// Модуль локальной БД (SQLCipher-шифрование, WAL).
// Хранит настройки программы, чаты и сообщения (с цитатами/ответами/вложениями).
//
// СХЕМА ВЕРСИОНИРУЕТСЯ через SQLite `PRAGMA user_version`.
// Каждое изменение архитектуры/новые настройки в будущем — это новая `if version < N { ... }`
// ветка в `migrate()`, никогда не переделывать уже выпущенные шаги — это гарантирует,
// что БД пользователя, созданная на старой версии приложения, безопасно доедет до актуальной,
// без потери данных.
//
// v3 (текущая): подготовка под будущую cloud-синхронизацию (сам синк ещё не реализован,
// это только схема + внутренний учёт изменений, ничего не отправляет и ни откуда не читает):
//   - `uuid` на chats/messages — стабильный межустройственный id (локальный `id` — это SQLite ROWID,
//     он не глобален и совпадёт на разных устройствах; uuid генерируется прямо в SQLite через
//     `lower(hex(randomblob(16)))`, чтобы не тянуть новую зависимость ради этого)
//   - `updated_at` на chats/messages — чтобы будущий синк знал, что изменилось с момента последней синхронизации
//   - таблица `tombstones` — без неё каскадное удаление стирает и сам факт удаления — другое
//     устройство при синке просто воскресит удалённое сообщение/чат, ничего не зная про delete.
//     Записы пишутся В delete_message/delete_chat/clear_chat_messages ДО фактического DELETE,
//     потому что uuid удаляемой строки нужно успеть прочитать до того, как он исчезнет.
// Ни один Python-вызывающий метод пока не читает эти колонки — UI и поведение не меняются.
// Сам синк-движок (чтение tombstones/updated_at, пуш/пулл на сервер) — следующий шаг, когда будет выбран транспорт/сервер.

use rusqlite::{params, Connection, OptionalExtension, Result};
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

/// Текущая версия схемы. Повышать при каждом изменении схемы и добавлять ветку в migrate().
const CURRENT_SCHEMA_VERSION: i32 = 3;

/// Одно сообщение со всеми полями: цитата/ответ — произвольный текст (не ссылка на другое сообщение по id),
/// вложения — список (имя_файла, путь_к_файлу).
#[derive(Debug, Clone)]
pub struct StoredMessage {
    pub id: i64,
    pub role: String,
    pub content: String,
    pub quote: Option<String>,
    pub reply_to: Option<String>,
    pub attachments: Vec<(String, String)>,
    pub created_at: i64,
}

pub struct Database {
    conn: Connection,
}

impl Database {
    /// Открывает (или создаёт) зашифрованную БД по пути и применяет миграции до актуальной схемы.
    /// `key` — ключ шифрования (генерируется из OS keyring на стороне модуля защиты — сюда приходит уже готовый хеш).
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

        if from_version < 2 {
            // Цитаты/ответы хранятся как произвольный текст (не FK на другое сообщение) —
            // совпадает с тем, как UI уже работает с цитатами/ответами (App/app/message.py).
            // Вложения — отдельная таблица, потому что их может быть несколько на сообщение.
            self.conn.execute_batch(
                "
                ALTER TABLE messages ADD COLUMN quote TEXT;
                ALTER TABLE messages ADD COLUMN reply_to TEXT;

                CREATE TABLE IF NOT EXISTS message_attachments (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id  INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                    name        TEXT NOT NULL,
                    path        TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_attachments_message_id ON message_attachments(message_id);
                ",
            )?;
        }

        if from_version < 3 {
            // Подготовка под будущий cloud-синк: uuid (стабильный межустройственный id, потому
            // что локальный `id` — это только SQLite ROWID этого устройства), updated_at
            // (что изменилось с последней синхронизации) и таблица tombstones (чтобы удаление
            // распространялось на другие устройства, а не терялось бесследно вместе со строкой).
            // Самого синка (передача на/с сервера) здесь ещё нет — только схема и внутренний учёт.
            self.conn.execute_batch(
                "
                ALTER TABLE chats ADD COLUMN uuid TEXT;
                ALTER TABLE chats ADD COLUMN updated_at INTEGER;
                ALTER TABLE messages ADD COLUMN uuid TEXT;
                ALTER TABLE messages ADD COLUMN updated_at INTEGER;

                CREATE TABLE IF NOT EXISTS tombstones (
                    entity_type  TEXT NOT NULL,   -- 'chat' | 'message'
                    entity_uuid  TEXT NOT NULL,
                    deleted_at   INTEGER NOT NULL,
                    PRIMARY KEY (entity_type, entity_uuid)
                );

                UPDATE chats SET uuid = lower(hex(randomblob(16))) WHERE uuid IS NULL;
                UPDATE chats SET updated_at = created_at WHERE updated_at IS NULL;
                UPDATE messages SET uuid = lower(hex(randomblob(16))) WHERE uuid IS NULL;
                UPDATE messages SET updated_at = created_at WHERE updated_at IS NULL;

                CREATE UNIQUE INDEX IF NOT EXISTS idx_chats_uuid ON chats(uuid);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_uuid ON messages(uuid);
                ",
            )?;
        }

        // Пример будущего шага:
        // if from_version < 4 { ... }

        Ok(())
    }

    /// Записывает факт удаления сущности для будущей синхронизации. Вызывать ДО фактического
    /// DELETE из chats/messages — иначе uuid удаляемой строки уже негде будет взять.
    fn record_tombstone(&self, entity_type: &str, entity_uuid: &str) -> Result<()> {
        self.conn.execute(
            "INSERT INTO tombstones (entity_type, entity_uuid, deleted_at) VALUES (?1, ?2, ?3)
             ON CONFLICT(entity_type, entity_uuid) DO UPDATE SET deleted_at = excluded.deleted_at",
            params![entity_type, entity_uuid, now()],
        )?;
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
        let now = now();
        self.conn.execute(
            "INSERT INTO chats (title, created_at, updated_at, uuid) VALUES (?1, ?2, ?2, lower(hex(randomblob(16))))",
            params![title, now],
        )?;
        Ok(self.conn.last_insert_rowid())
    }

    /// Простое сообщение без цитат/вложений — тонкая обёртка над add_message_full.
    // pub fn add_message(&self, chat_id: i64, role: &str, content: &str) -> Result<i64> {
    //     self.add_message_full(chat_id, role, content, None, None, &[])
    // }
    // пока что закоменчу

    /// Полная версия: с цитатой/ответом и списком вложений (имя, путь).
    pub fn add_message_full(
        &self,
        chat_id: i64,
        role: &str,
        content: &str,
        quote: Option<&str>,
        reply_to: Option<&str>,
        attachments: &[(String, String)],
    ) -> Result<i64> {
        let now = now();
        self.conn.execute(
            "INSERT INTO messages (chat_id, role, content, quote, reply_to, created_at, updated_at, uuid)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?6, lower(hex(randomblob(16))))",
            params![chat_id, role, content, quote, reply_to, now],
        )?;
        let message_id = self.conn.last_insert_rowid();

        for (name, path) in attachments {
            self.conn.execute(
                "INSERT INTO message_attachments (message_id, name, path) VALUES (?1, ?2, ?3)",
                params![message_id, name, path],
            )?;
        }

        Ok(message_id)
    }

    /// Правит текст уже отправленного сообщения (редактирование в UI). Цитату/ответ/вложения пока не трогает (известное ограничение, будет расширено при необходимости).
    /// Бумает updated_at — без этого будущий синк не увидит правку как изменение.
    /// Возвращает Ok(false), если сообщение с таким id не найдено.
    pub fn update_message(&self, message_id: i64, content: &str) -> Result<bool> {
        let affected = self.conn.execute(
            "UPDATE messages SET content = ?1, updated_at = ?2 WHERE id = ?3",
            params![content, now(), message_id],
        )?;
        Ok(affected > 0)
    }

    pub fn get_messages(&self, chat_id: i64) -> Result<Vec<StoredMessage>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, role, content, quote, reply_to, created_at FROM messages WHERE chat_id = ?1 ORDER BY id ASC",
        )?;
        let rows = stmt.query_map(params![chat_id], |row| {
            Ok(StoredMessage {
                id: row.get(0)?,
                role: row.get(1)?,
                content: row.get(2)?,
                quote: row.get(3)?,
                reply_to: row.get(4)?,
                attachments: Vec::new(),
                created_at: row.get(5)?,
            })
        })?;
        let mut messages = rows.collect::<Result<Vec<_>>>()?;

        // N+1 на вложения — нормально для локального десктопа и типичного размера чата; при необходимости легко заменить на JOIN.
        let mut attach_stmt = self
            .conn
            .prepare("SELECT name, path FROM message_attachments WHERE message_id = ?1 ORDER BY id ASC")?;
        for message in messages.iter_mut() {
            let attachments = attach_stmt
                .query_map(params![message.id], |row| Ok((row.get(0)?, row.get(1)?)))?
                .collect::<Result<Vec<_>>>()?;
            message.attachments = attachments;
        }

        Ok(messages)
    }

    pub fn list_chats(&self) -> Result<Vec<(i64, String, i64)>> {
        let mut stmt = self
            .conn
            .prepare("SELECT id, COALESCE(title, ''), created_at FROM chats ORDER BY created_at DESC")?;
        let rows = stmt.query_map([], |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)))?;
        rows.collect()
    }

    /// Удаляет все сообщения чата (вложения удаляются каскадно через FK). Сам чат остаётся.
    /// Пишет tombstone на каждое удаляемое сообщение — без этого будущий синк воскресил бы их с другого устройства.
    pub fn clear_chat_messages(&self, chat_id: i64) -> Result<()> {
        let message_uuids = self.message_uuids_of_chat(chat_id)?;
        self.conn
            .execute("DELETE FROM messages WHERE chat_id = ?1", params![chat_id])?;
        for uuid in message_uuids {
            self.record_tombstone("message", &uuid)?;
        }
        Ok(())
    }

    /// Удаляет ровно одно сообщение; связанные вложения удаляются через FK. Пишет tombstone для будущего синка.
    pub fn delete_message(&self, message_id: i64) -> Result<bool> {
        // uuid нужно успеть прочитать ДО удаления — после DELETE строки уже нет.
        let uuid: Option<String> = self
            .conn
            .query_row("SELECT uuid FROM messages WHERE id = ?1", params![message_id], |row| row.get(0))
            .optional()?;
        let affected = self.conn.execute("DELETE FROM messages WHERE id = ?1", params![message_id])?;
        if let Some(uuid) = uuid {
            self.record_tombstone("message", &uuid)?;
        }
        Ok(affected > 0)
    }

    /// Удаляет чат целиком: связанные сообщения и их вложения удаляются каскадно через FK
    /// (ON DELETE CASCADE на messages.chat_id и message_attachments.message_id). Пишет tombstone и на сам чат,
    /// и на каждое его сообщение — иначе другое устройство при синхронизации увидит только пропавший чат,
    /// а его сообщения без tombstone могут остаться «висеть» на нём при push.
    /// Возвращает Ok(false), если чата с таким id не было.
    pub fn delete_chat(&self, chat_id: i64) -> Result<bool> {
        let chat_uuid: Option<String> = self
            .conn
            .query_row("SELECT uuid FROM chats WHERE id = ?1", params![chat_id], |row| row.get(0))
            .optional()?;
        let message_uuids = self.message_uuids_of_chat(chat_id)?;

        let affected = self.conn.execute("DELETE FROM chats WHERE id = ?1", params![chat_id])?;

        if let Some(uuid) = chat_uuid {
            self.record_tombstone("chat", &uuid)?;
        }
        for uuid in message_uuids {
            self.record_tombstone("message", &uuid)?;
        }
        Ok(affected > 0)
    }

    fn message_uuids_of_chat(&self, chat_id: i64) -> Result<Vec<String>> {
        let mut stmt = self.conn.prepare("SELECT uuid FROM messages WHERE chat_id = ?1")?;
        let rows = stmt.query_map(params![chat_id], |row| row.get(0))?;
        rows.collect()
    }

    /// Общее число сообщений во всех чатах — для статистики на странице «Аккаунт».
    pub fn total_message_count(&self) -> Result<i64> {
        self.conn
            .query_row("SELECT COUNT(*) FROM messages", [], |row| row.get(0))
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