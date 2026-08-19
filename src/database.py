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
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_type TEXT NOT NULL DEFAULT 'chatgpt',
    source_id TEXT,
    source_archive TEXT
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
    source_type TEXT NOT NULL DEFAULT 'chatgpt',
    source_archive TEXT,

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

SOURCE_INDEX_SCHEMA = """
CREATE INDEX IF NOT EXISTS idx_conversations_source_type
    ON conversations(source_type);

CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_source_identity
    ON conversations(source_type, source_id)
    WHERE source_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_messages_source_type
    ON messages(source_type);
"""

SOURCE_TRIGGER_SCHEMA = """
CREATE TRIGGER IF NOT EXISTS trg_conversations_default_source_id
AFTER INSERT ON conversations
WHEN NEW.source_id IS NULL
BEGIN
    UPDATE conversations
    SET source_id = NEW.id
    WHERE id = NEW.id;
END;
"""


def connect(db_path: Path = DEFAULT_DB) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")

    return connection


def _column_names(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    rows = connection.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()
    return {str(row[1]) for row in rows}


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> bool:
    columns = _column_names(connection, table_name)
    if column_name in columns:
        return False

    connection.execute(
        f'ALTER TABLE "{table_name}" '
        f'ADD COLUMN "{column_name}" {column_definition}'
    )
    return True


def migrate_multisource_schema(
    connection: sqlite3.Connection,
) -> list[str]:
    """
    Idempotently extend the original WyrmMango v0.1 schema for
    multi-source provenance without replacing existing tables.

    Existing rows are classified as ChatGPT because v0.1 only imported
    ChatGPT exports. The original source_file and raw_json fields remain
    untouched.
    """
    changes: list[str] = []

    additions = (
        (
            "conversations",
            "source_type",
            "TEXT NOT NULL DEFAULT 'chatgpt'",
        ),
        (
            "conversations",
            "source_id",
            "TEXT",
        ),
        (
            "conversations",
            "source_archive",
            "TEXT",
        ),
        (
            "messages",
            "source_type",
            "TEXT NOT NULL DEFAULT 'chatgpt'",
        ),
        (
            "messages",
            "source_archive",
            "TEXT",
        ),
    )

    for table_name, column_name, definition in additions:
        if _ensure_column(
            connection,
            table_name,
            column_name,
            definition,
        ):
            changes.append(f"{table_name}.{column_name}")

    # The original application only imported ChatGPT. Backfill source_id
    # from the existing primary key for all legacy conversation rows.
    connection.execute(
        """
        UPDATE conversations
        SET source_id = id
        WHERE source_id IS NULL
          AND source_type = 'chatgpt'
        """
    )

    connection.executescript(SOURCE_INDEX_SCHEMA)
    connection.executescript(SOURCE_TRIGGER_SCHEMA)
    connection.commit()

    return changes


def initialize_database(
    db_path: Path = DEFAULT_DB,
) -> sqlite3.Connection:
    connection = connect(db_path)

    connection.executescript(SCHEMA)
    migrate_multisource_schema(connection)

    try:
        connection.executescript(FTS_SCHEMA)

    except sqlite3.OperationalError as exc:
        connection.close()

        raise RuntimeError(
            "SQLite FTS5 is not available in this Python installation."
        ) from exc

    connection.commit()

    return connection


def rebuild_fts(
    connection: sqlite3.Connection,
) -> int:
    """Rebuild the existing shared FTS5 index from all message sources."""
    connection.execute("DELETE FROM messages_fts;")
    connection.execute(
        """
        INSERT INTO messages_fts (
            content,
            role,
            conversation_title,
            conversation_id,
            message_rowid
        )
        SELECT
            COALESCE(m.content, ''),
            COALESCE(m.role, ''),
            COALESCE(c.title, ''),
            m.conversation_id,
            m.id
        FROM messages AS m
        JOIN conversations AS c
          ON c.id = m.conversation_id
        WHERE m.content IS NOT NULL
          AND TRIM(m.content) <> ''
        """
    )
    connection.commit()

    count = connection.execute(
        "SELECT COUNT(*) FROM messages_fts;"
    ).fetchone()[0]
    return int(count)


def verify_database(
    connection: sqlite3.Connection,
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
