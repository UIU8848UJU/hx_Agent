PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  chunk_policy_version TEXT NOT NULL,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL UNIQUE,
  mtime INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  size INTEGER NOT NULL,
  type TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id INTEGER NOT NULL,
  chunk_index INTEGER NOT NULL,
  heading TEXT,
  start_offset INTEGER,
  end_offset INTEGER,
  text TEXT NOT NULL,
  text_hash TEXT NOT NULL,
  chunk_policy_version TEXT NOT NULL,
  FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
);

-- FTS5: 用于全文检索（关键词/代码/路径都很强）
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
USING fts5(
  text,
  path UNINDEXED,
  heading UNINDEXED,
  content='',
  tokenize='unicode61'
);

CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_chunks_text_hash ON chunks(text_hash);
