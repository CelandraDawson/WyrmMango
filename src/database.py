from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DB = DATA_DIR / "chatarchive.sqlite"


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    create_time REAL,
    update_time REAL,
    current_node TEXT,
    source_file TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    conversation_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    message_id TEXT,

    parent_node_id TEXT,

    role TEXT,
    author_name TEXT,

    create_time REAL,
    update_time REAL,

    status TEXT,
    model_slug TEXT,
    content_type TEXT,

    content TEXT,

    metadata_json TEXT,
    raw_json TEXT NOT NULL,

    source_file TEXT NOT NULL,

    FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    UNIQUE(conversation_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id);

CREATE INDEX IF NOT EXISTS idx_messages_role
    ON messages(role);

CREATE INDEX IF NOT EXISTS idx_messages_create_time
    ON messages(create_time);

CREATE INDEX IF NOT EXISTS idx_messages_model
    ON messages(model_slug);

CREATE INDEX IF NOT EXISTS idx_messages_node
    ON messages(node_id);

CREATE INDEX IF NOT EXISTS idx_conversations_create_time
    ON conversations(create_time);

CREATE INDEX IF NOT EXISTS idx_conversations_title
    ON conversations(title);
"""


FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
USING fts5(
    content,
    role,
    conversation_title,
    conversation_id UNINDEXED,
    message_rowid UNINDEXED
);
"""


def connect(db_path: Path = DEFAULT_DB) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")

    return connection


def initialize_database(
    db_path: Path = DEFAULT_DB
) -> sqlite3.Connection:

    connection = connect(db_path)

    connection.executescript(SCHEMA)

    try:
        connection.executescript(FTS_SCHEMA)

    except sqlite3.OperationalError as exc:

        connection.close()

        raise RuntimeError(
            "SQLite FTS5 is not available in this Python installation."
        ) from exc

    connection.commit()

    return connection


def verify_database(
    connection: sqlite3.Connection
) -> None:

    integrity = connection.execute(
        "PRAGMA integrity_check;"
    ).fetchone()[0]

    if integrity != "ok":
        raise RuntimeError(
            f"SQLite integrity check failed: {integrity}"
        )

    fts_count = connection.execute(
        "SELECT count(*) FROM messages_fts;"
    ).fetchone()[0]

    print("SQLite database initialized successfully.")
    print(f"Database: {DEFAULT_DB}")
    print(f"Integrity check: {integrity}")
    print("FTS5 full-text search: AVAILABLE")
    print(f"FTS rows: {fts_count}")


if __name__ == "__main__":

    db = initialize_database()

    try:
        verify_database(db)

    finally:
        db.close()
