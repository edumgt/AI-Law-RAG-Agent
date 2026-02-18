const fs = require("fs");
const path = require("path");
const Database = require("better-sqlite3");

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function initDb(sqlitePath) {
  const abs = path.isAbsolute(sqlitePath) ? sqlitePath : path.join(process.cwd(), sqlitePath);
  ensureDir(path.dirname(abs));
  const db = new Database(abs);
  db.pragma("journal_mode = WAL");

  // Base schema (v1)
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      email TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      client_id TEXT NOT NULL UNIQUE,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS chunks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      source TEXT NOT NULL,
      doc_type TEXT NOT NULL,
      title TEXT,
      text TEXT NOT NULL,
      embedding_json TEXT NOT NULL,
      meta_json TEXT NOT NULL,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS chats (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      client_id TEXT NOT NULL,
      question TEXT NOT NULL,
      answer TEXT NOT NULL,
      citations_json TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
  `);

  // Migrations (safe, idempotent)
  migrate(db);

  return db;
}

function hasColumn(db, table, column) {
  const cols = db.prepare(`PRAGMA table_info(${table})`).all();
  return cols.some((c) => c.name === column);
}
function hasTable(db, table) {
  const t = db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name=?").get(table);
  return !!t;
}

function migrate(db) {
  // chunks: add versioning fields (v2+)
  if (!hasColumn(db, "chunks", "doc_id")) db.exec(`ALTER TABLE chunks ADD COLUMN doc_id TEXT`);
  if (!hasColumn(db, "chunks", "doc_version")) db.exec(`ALTER TABLE chunks ADD COLUMN doc_version INTEGER`);
  if (!hasColumn(db, "chunks", "effective_date")) db.exec(`ALTER TABLE chunks ADD COLUMN effective_date TEXT`);
  if (!hasColumn(db, "chunks", "jurisdiction")) db.exec(`ALTER TABLE chunks ADD COLUMN jurisdiction TEXT`);
  if (!hasColumn(db, "chunks", "content_hash")) db.exec(`ALTER TABLE chunks ADD COLUMN content_hash TEXT`);
  if (!hasColumn(db, "chunks", "chunk_index")) db.exec(`ALTER TABLE chunks ADD COLUMN chunk_index INTEGER`);
  if (!hasColumn(db, "chunks", "doc_row_id")) db.exec(`ALTER TABLE chunks ADD COLUMN doc_row_id INTEGER`);

  // Users: optional 'primary_role' cache
  if (!hasColumn(db, "users", "primary_role")) db.exec(`ALTER TABLE users ADD COLUMN primary_role TEXT`);

  // Roles + user_roles
  if (!hasTable(db, "roles")) {
    db.exec(`
      CREATE TABLE roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
      );
    `);
    db.prepare("INSERT OR IGNORE INTO roles(name) VALUES (?)").run("user");
    db.prepare("INSERT OR IGNORE INTO roles(name) VALUES (?)").run("admin");
  } else {
    db.prepare("INSERT OR IGNORE INTO roles(name) VALUES (?)").run("user");
    db.prepare("INSERT OR IGNORE INTO roles(name) VALUES (?)").run("admin");
  }

  if (!hasTable(db, "user_roles")) {
    db.exec(`
      CREATE TABLE user_roles (
        user_id INTEGER NOT NULL,
        role_name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY(user_id, role_name),
        FOREIGN KEY(user_id) REFERENCES users(id)
      );
    `);
  }

  // docs table (normalized doc metadata & ACL)
  if (!hasTable(db, "docs")) {
    db.exec(`
      CREATE TABLE docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id TEXT NOT NULL,
        doc_version INTEGER NOT NULL,
        doc_type TEXT NOT NULL,
        title TEXT,
        source TEXT NOT NULL,
        jurisdiction TEXT,
        effective_date TEXT,
        allowed_roles_json TEXT NOT NULL,
        meta_json TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(doc_id, doc_version)
      );
    `);
  }

  // doc_roles (optional expanded ACL; kept simple with docs.allowed_roles_json)

  // Audit events
  if (!hasTable(db, "audit_events")) {
    db.exec(`
      CREATE TABLE audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        client_id TEXT,
        event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
      );
    `);
  }

  // Indices
  try { db.exec(`CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id, doc_version)`); } catch {}
  try { db.exec(`CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(content_hash)`); } catch {}
  try { db.exec(`CREATE INDEX IF NOT EXISTS idx_docs_key ON docs(doc_id, doc_version)`); } catch {}
  try { db.exec(`CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_events(user_id, created_at)`); } catch {}
}

module.exports = { initDb };
