from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterable

from database import DEFAULT_DB, initialize_database


CONVERSATION_FILE_RE = re.compile(
    r"(^|/)conversations(?:-\d+)?\.json$",
    re.IGNORECASE,
)


def json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def extract_content_text(content: Any) -> str:
    """
    Extract searchable human-readable text from a ChatGPT message.

    The complete original message remains preserved separately in raw_json.
    """
    if not isinstance(content, dict):
        return ""

    pieces: list[str] = []

    parts = content.get("parts")

    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, str):
                pieces.append(part)

            elif isinstance(part, dict):
                text = part.get("text")

                if isinstance(text, str):
                    pieces.append(text)

                elif isinstance(text, list):
                    pieces.extend(
                        str(x) for x in text
                        if isinstance(x, (str, int, float))
                    )

    text_value = content.get("text")

    if isinstance(text_value, str):
        pieces.append(text_value)

    return "\n".join(
        piece for piece in pieces
        if piece and piece.strip()
    )


def discover_zip_files(
    zip_path: Path,
) -> list[str]:

    with zipfile.ZipFile(zip_path, "r") as archive:

        names = [
            info.filename
            for info in archive.infolist()
            if not info.is_dir()
            and CONVERSATION_FILE_RE.search(
                info.filename.replace("\\", "/")
            )
        ]

    return sorted(names)


def discover_directory_files(
    directory: Path,
) -> list[Path]:

    files: list[Path] = []

    for path in directory.rglob("*.json"):

        normalized = path.as_posix()

        if CONVERSATION_FILE_RE.search(normalized):
            files.append(path)

    return sorted(files)


def load_json_from_zip(
    zip_path: Path,
    member_name: str,
) -> Any:

    with zipfile.ZipFile(zip_path, "r") as archive:
        with archive.open(member_name, "r") as raw:
            return json.load(raw)


def load_json_file(
    path: Path,
) -> Any:

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        return json.load(handle)


def normalize_conversation_list(
    payload: Any,
) -> list[dict[str, Any]]:

    if isinstance(payload, list):
        return [
            item
            for item in payload
            if isinstance(item, dict)
        ]

    if isinstance(payload, dict):

        for key in (
            "conversations",
            "items",
            "data",
        ):
            value = payload.get(key)

            if isinstance(value, list):
                return [
                    item
                    for item in value
                    if isinstance(item, dict)
                ]

    raise ValueError(
        "Conversation JSON does not contain a recognizable "
        "conversation list."
    )


def upsert_conversation(
    connection: sqlite3.Connection,
    conversation: dict[str, Any],
    source_file: str,
    conversation_index: int,
) -> tuple[str, int]:

    conversation_id = (
        conversation.get("id")
        or conversation.get("conversation_id")
        or f"{source_file}:{conversation_index}"
    )

    conversation_id = str(conversation_id)

    title = conversation.get("title")

    create_time = conversation.get("create_time")
    update_time = conversation.get("update_time")
    current_node = conversation.get("current_node")

    raw_conversation = json_text(conversation)

    connection.execute(
        """
        INSERT INTO conversations (
            id,
            title,
            create_time,
            update_time,
            current_node,
            source_file,
            raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            create_time = excluded.create_time,
            update_time = excluded.update_time,
            current_node = excluded.current_node,
            source_file = excluded.source_file,
            raw_json = excluded.raw_json
        """,
        (
            conversation_id,
            title,
            create_time,
            update_time,
            current_node,
            source_file,
            raw_conversation,
        ),
    )

    mapping = conversation.get("mapping")

    if not isinstance(mapping, dict):
        return conversation_id, 0

    message_count = 0

    for node_key, node in mapping.items():

        if not isinstance(node, dict):
            continue

        node_id = str(
            node.get("id")
            or node_key
        )

        parent_node_id = node.get("parent")

        if parent_node_id is not None:
            parent_node_id = str(parent_node_id)

        message = node.get("message")

        if not isinstance(message, dict):
            continue

        message_id = message.get("id")

        if message_id is not None:
            message_id = str(message_id)

        author = message.get("author")

        if not isinstance(author, dict):
            author = {}

        role = author.get("role")
        author_name = author.get("name")

        create_time = message.get("create_time")
        update_time = message.get("update_time")
        status = message.get("status")

        content = message.get("content")

        if not isinstance(content, dict):
            content = {}

        content_type = content.get("content_type")
        content_text = extract_content_text(content)

        metadata = message.get("metadata")

        if not isinstance(metadata, dict):
            metadata = {}

        model_slug = (
            metadata.get("model_slug")
            or metadata.get("default_model_slug")
        )

        connection.execute(
            """
            INSERT INTO messages (
                conversation_id,
                node_id,
                message_id,
                parent_node_id,
                role,
                author_name,
                create_time,
                update_time,
                status,
                model_slug,
                content_type,
                content,
                metadata_json,
                raw_json,
                source_file
            )
            VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?
            )

            ON CONFLICT(
                conversation_id,
                node_id
            )
            DO UPDATE SET
                message_id = excluded.message_id,
                parent_node_id = excluded.parent_node_id,
                role = excluded.role,
                author_name = excluded.author_name,
                create_time = excluded.create_time,
                update_time = excluded.update_time,
                status = excluded.status,
                model_slug = excluded.model_slug,
                content_type = excluded.content_type,
                content = excluded.content,
                metadata_json = excluded.metadata_json,
                raw_json = excluded.raw_json,
                source_file = excluded.source_file
            """,
            (
                conversation_id,
                node_id,
                message_id,
                parent_node_id,
                role,
                author_name,
                create_time,
                update_time,
                status,
                model_slug,
                content_type,
                content_text,
                json_text(metadata),
                json_text(node),
                source_file,
            ),
        )

        message_count += 1

    return conversation_id, message_count


def import_payload(
    connection: sqlite3.Connection,
    payload: Any,
    source_file: str,
) -> tuple[int, int]:

    conversations = normalize_conversation_list(
        payload
    )

    conversation_count = 0
    message_count = 0

    for index, conversation in enumerate(
        conversations,
        start=1,
    ):

        _, count = upsert_conversation(
            connection,
            conversation,
            source_file,
            index,
        )

        conversation_count += 1
        message_count += count

        if index % 100 == 0:
            print(
                f"    Processed "
                f"{index:,} conversations...",
                flush=True,
            )

    connection.commit()

    return conversation_count, message_count


def rebuild_fts(
    connection: sqlite3.Connection,
) -> int:

    print()
    print("Rebuilding FTS5 search index...")

    connection.execute(
        "DELETE FROM messages_fts;"
    )

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

        WHERE
            m.content IS NOT NULL
            AND TRIM(m.content) <> ''
        """
    )

    connection.commit()

    count = connection.execute(
        "SELECT COUNT(*) FROM messages_fts;"
    ).fetchone()[0]

    return int(count)


def verify_import(
    connection: sqlite3.Connection,
) -> None:

    conversations = connection.execute(
        "SELECT COUNT(*) FROM conversations;"
    ).fetchone()[0]

    messages = connection.execute(
        "SELECT COUNT(*) FROM messages;"
    ).fetchone()[0]

    searchable = connection.execute(
        "SELECT COUNT(*) FROM messages_fts;"
    ).fetchone()[0]

    integrity = connection.execute(
        "PRAGMA integrity_check;"
    ).fetchone()[0]

    print()
    print("===== IMPORT SUMMARY =====")
    print(
        f"Conversations: {conversations:,}"
    )
    print(
        f"Messages:      {messages:,}"
    )
    print(
        f"FTS rows:      {searchable:,}"
    )
    print(
        f"Integrity:     {integrity}"
    )


def import_zip(
    connection: sqlite3.Connection,
    zip_path: Path,
) -> None:

    files = discover_zip_files(zip_path)

    if not files:
        raise RuntimeError(
            "No conversations*.json files "
            "were found in the ZIP."
        )

    print(
        f"Conversation files found: {len(files)}"
    )

    for index, member in enumerate(
        files,
        start=1,
    ):

        print()
        print(
            f"[{index}/{len(files)}] "
            f"Importing {member}"
        )

        payload = load_json_from_zip(
            zip_path,
            member,
        )

        conversations, messages = import_payload(
            connection,
            payload,
            member,
        )

        print(
            f"    Conversations: "
            f"{conversations:,}"
        )

        print(
            f"    Message nodes: "
            f"{messages:,}"
        )


def import_directory(
    connection: sqlite3.Connection,
    directory: Path,
) -> None:

    files = discover_directory_files(directory)

    if not files:
        raise RuntimeError(
            "No conversations*.json files "
            "were found in the directory."
        )

    print(
        f"Conversation files found: {len(files)}"
    )

    for index, path in enumerate(
        files,
        start=1,
    ):

        print()
        print(
            f"[{index}/{len(files)}] "
            f"Importing {path.name}"
        )

        payload = load_json_file(path)

        conversations, messages = import_payload(
            connection,
            payload,
            path.name,
        )

        print(
            f"    Conversations: "
            f"{conversations:,}"
        )

        print(
            f"    Message nodes: "
            f"{messages:,}"
        )


def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Import a ChatGPT data export into "
            "a local SQLite archive."
        )
    )

    parser.add_argument(
        "source",
        help=(
            "Path to the ChatGPT export ZIP "
            "or an extracted export directory."
        ),
    )

    parser.add_argument(
        "--database",
        default=str(DEFAULT_DB),
        help=(
            "SQLite database path. "
            "Defaults to data/chatarchive.sqlite."
        ),
    )

    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    db_path = Path(args.database).expanduser().resolve()

    if not source.exists():
        print(
            f"ERROR: Source does not exist: "
            f"{source}",
            file=sys.stderr,
        )
        return 1

    print("ChatArchive Importer")
    print("====================")
    print(f"Source:   {source}")
    print(f"Database: {db_path}")
    print()

    connection = initialize_database(
        db_path
    )

    try:

        if source.is_file():

            if not zipfile.is_zipfile(source):
                raise RuntimeError(
                    "Source file is not a valid ZIP archive."
                )

            import_zip(
                connection,
                source,
            )

        elif source.is_dir():

            import_directory(
                connection,
                source,
            )

        else:
            raise RuntimeError(
                "Source must be a ZIP file "
                "or directory."
            )

        fts_count = rebuild_fts(
            connection
        )

        print(
            f"FTS5 indexed messages: "
            f"{fts_count:,}"
        )

        verify_import(
            connection
        )

    finally:
        connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
