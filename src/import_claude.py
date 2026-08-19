from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from database import DEFAULT_DB, initialize_database, rebuild_fts


SOURCE_TYPE = "claude"
CONVERSATIONS_FILENAME = "conversations.json"


def json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def iso_to_epoch(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.timestamp()


def _append_unique(parts: list[str], value: Any) -> None:
    if not isinstance(value, str):
        return

    text = value.strip()
    if not text:
        return

    if text not in parts:
        parts.append(text)


def _append_visible_structured_text(
    parts: list[str],
    value: Any,
) -> None:
    """
    Extract conservative, human-readable text from Claude structured
    content without indexing explicitly hidden content.
    """
    if isinstance(value, str):
        _append_unique(parts, value)
        return

    if isinstance(value, list):
        for item in value:
            _append_visible_structured_text(parts, item)
        return

    if not isinstance(value, dict):
        return

    if value.get("hidden") is True or value.get("hidden_in_chat") is True:
        return

    for key in ("text", "display_content", "message"):
        _append_unique(parts, value.get(key))

    content = value.get("content")
    if isinstance(content, (str, list, dict)):
        _append_visible_structured_text(parts, content)


def extract_searchable_text(message: dict[str, Any]) -> str:
    """
    Build searchable text while preserving the full original message in
    raw_json. Top-level Claude message text is primary. Visible structured
    content and extracted attachment text are included when present.
    """
    parts: list[str] = []

    _append_unique(parts, message.get("text"))

    structured = message.get("content")
    if isinstance(structured, list):
        _append_visible_structured_text(parts, structured)

    attachments = message.get("attachments")
    if isinstance(attachments, list):
        for attachment in attachments:
            if not isinstance(attachment, dict):
                continue
            _append_unique(parts, attachment.get("file_name"))
            _append_unique(parts, attachment.get("extracted_content"))

    files = message.get("files")
    if isinstance(files, list):
        for file_entry in files:
            if not isinstance(file_entry, dict):
                continue
            _append_unique(parts, file_entry.get("file_name"))

    return "\n\n".join(parts)


def message_metadata(message: dict[str, Any]) -> dict[str, Any]:
    """Preserve compact useful metadata without duplicating attachment text."""
    result: dict[str, Any] = {
        "source_type": SOURCE_TYPE,
        "sender": message.get("sender"),
    }

    attachments = message.get("attachments")
    if isinstance(attachments, list):
        compact_attachments: list[dict[str, Any]] = []
        for attachment in attachments:
            if not isinstance(attachment, dict):
                continue
            compact_attachments.append(
                {
                    key: attachment.get(key)
                    for key in (
                        "file_name",
                        "file_size",
                        "file_type",
                    )
                    if key in attachment
                }
            )
        if compact_attachments:
            result["attachments"] = compact_attachments

    files = message.get("files")
    if isinstance(files, list) and files:
        result["files"] = files

    return result


def normalize_role(sender: Any) -> str | None:
    if not isinstance(sender, str):
        return None

    normalized = sender.strip().lower()
    if normalized == "human":
        return "user"
    if normalized == "assistant":
        return "assistant"
    return normalized or None


def validate_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError(
            "Claude conversations.json must contain a top-level list."
        )

    conversations = [
        item for item in payload if isinstance(item, dict)
    ]

    if payload and not conversations:
        raise ValueError(
            "Claude conversations.json did not contain conversation objects."
        )

    if conversations:
        required = {"uuid", "chat_messages"}
        if not required.issubset(conversations[0].keys()):
            raise ValueError(
                "The selected conversations.json does not match the verified "
                "Claude export structure (uuid + chat_messages)."
            )

    return conversations


def discover_zip_member(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path, "r") as archive:
        candidates = [
            info.filename
            for info in archive.infolist()
            if not info.is_dir()
            and Path(info.filename.replace("\\", "/")).name.lower()
            == CONVERSATIONS_FILENAME
        ]

    if len(candidates) != 1:
        raise RuntimeError(
            "Expected exactly one conversations.json in the Claude ZIP; "
            f"found {len(candidates)}."
        )

    return candidates[0]


def load_source(source: Path) -> tuple[list[dict[str, Any]], str, str]:
    """
    Return (conversations, source_file, source_archive).
    Supports either an Anthropic ZIP or an extracted export directory.
    """
    if source.is_file():
        if not zipfile.is_zipfile(source):
            raise RuntimeError("Claude source file is not a valid ZIP archive.")

        member = discover_zip_member(source)
        with zipfile.ZipFile(source, "r") as archive:
            with archive.open(member, "r") as raw:
                payload = json.load(raw)

        return validate_payload(payload), member, source.name

    if source.is_dir():
        path = source / CONVERSATIONS_FILENAME
        if not path.exists():
            candidates = list(source.rglob(CONVERSATIONS_FILENAME))
            if len(candidates) != 1:
                raise RuntimeError(
                    "Expected exactly one conversations.json in the Claude "
                    f"export directory; found {len(candidates)}."
                )
            path = candidates[0]

        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        try:
            source_file = str(path.relative_to(source))
        except ValueError:
            source_file = path.name

        return validate_payload(payload), source_file, source.name

    raise RuntimeError("Claude source must be a ZIP file or directory.")


def upsert_conversation(
    connection: sqlite3.Connection,
    conversation: dict[str, Any],
    source_file: str,
    source_archive: str,
) -> int:
    source_id = conversation.get("uuid")
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("Claude conversation is missing its required uuid.")

    source_id = source_id.strip()
    conversation_id = f"claude:{source_id}"

    title = conversation.get("name")
    if not isinstance(title, str) or not title.strip():
        title = "Untitled Claude Conversation"

    create_time = iso_to_epoch(conversation.get("created_at"))
    update_time = iso_to_epoch(conversation.get("updated_at"))

    messages = conversation.get("chat_messages")
    if not isinstance(messages, list):
        messages = []

    connection.execute(
        """
        INSERT INTO conversations (
            id,
            title,
            create_time,
            update_time,
            current_node,
            source_file,
            raw_json,
            source_type,
            source_id,
            source_archive
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            create_time = excluded.create_time,
            update_time = excluded.update_time,
            current_node = excluded.current_node,
            source_file = excluded.source_file,
            raw_json = excluded.raw_json,
            source_type = excluded.source_type,
            source_id = excluded.source_id,
            source_archive = excluded.source_archive
        """,
        (
            conversation_id,
            title,
            create_time,
            update_time,
            None,
            source_file,
            json_text(conversation),
            SOURCE_TYPE,
            source_id,
            source_archive,
        ),
    )

    imported_messages = 0

    for message in messages:
        if not isinstance(message, dict):
            continue

        message_uuid = message.get("uuid")
        if not isinstance(message_uuid, str) or not message_uuid.strip():
            raise ValueError(
                f"Claude conversation {source_id} contains a message "
                "without a uuid."
            )

        message_uuid = message_uuid.strip()
        node_id = f"claude:{message_uuid}"

        parent_uuid = message.get("parent_message_uuid")
        parent_node_id = None
        if isinstance(parent_uuid, str) and parent_uuid.strip():
            parent_node_id = f"claude:{parent_uuid.strip()}"

        sender = message.get("sender")
        role = normalize_role(sender)
        content_text = extract_searchable_text(message)

        content_type = "text" if content_text.strip() else "structured"

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
                source_file,
                source_type,
                source_archive
            )
            VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
            ON CONFLICT(conversation_id, node_id)
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
                source_file = excluded.source_file,
                source_type = excluded.source_type,
                source_archive = excluded.source_archive
            """,
            (
                conversation_id,
                node_id,
                message_uuid,
                parent_node_id,
                role,
                str(sender) if sender is not None else None,
                iso_to_epoch(message.get("created_at")),
                iso_to_epoch(message.get("updated_at")),
                None,
                None,
                content_type,
                content_text,
                json_text(message_metadata(message)),
                json_text(message),
                source_file,
                SOURCE_TYPE,
                source_archive,
            ),
        )
        imported_messages += 1

    return imported_messages


def import_conversations(
    connection: sqlite3.Connection,
    conversations: Iterable[dict[str, Any]],
    source_file: str,
    source_archive: str,
) -> tuple[int, int]:
    conversation_count = 0
    message_count = 0

    for conversation_count, conversation in enumerate(
        conversations,
        start=1,
    ):
        message_count += upsert_conversation(
            connection,
            conversation,
            source_file,
            source_archive,
        )

        if conversation_count % 25 == 0:
            print(
                f"    Processed {conversation_count:,} conversations...",
                flush=True,
            )

    connection.commit()
    return conversation_count, message_count


def verify_import(
    connection: sqlite3.Connection,
    expected_conversations: int,
    expected_messages: int,
) -> None:
    source_conversations = connection.execute(
        """
        SELECT COUNT(*)
        FROM conversations
        WHERE source_type = ?
        """,
        (SOURCE_TYPE,),
    ).fetchone()[0]

    source_messages = connection.execute(
        """
        SELECT COUNT(*)
        FROM messages
        WHERE source_type = ?
        """,
        (SOURCE_TYPE,),
    ).fetchone()[0]

    integrity = connection.execute(
        "PRAGMA integrity_check;"
    ).fetchone()[0]

    orphan_messages = connection.execute(
        """
        SELECT COUNT(*)
        FROM messages AS m
        LEFT JOIN conversations AS c
          ON c.id = m.conversation_id
        WHERE c.id IS NULL
        """
    ).fetchone()[0]

    if integrity != "ok":
        raise RuntimeError(f"SQLite integrity check failed: {integrity}")

    if source_conversations != expected_conversations:
        raise RuntimeError(
            "Claude conversation verification failed: "
            f"expected {expected_conversations}, found {source_conversations}."
        )

    if source_messages != expected_messages:
        raise RuntimeError(
            "Claude message verification failed: "
            f"expected {expected_messages}, found {source_messages}."
        )

    if orphan_messages != 0:
        raise RuntimeError(
            f"Foreign-key verification found {orphan_messages} orphan messages."
        )

    print()
    print("===== CLAUDE IMPORT VERIFICATION =====")
    print(f"Claude conversations: {source_conversations:,}")
    print(f"Claude messages:      {source_messages:,}")
    print(f"Orphan messages:      {orphan_messages:,}")
    print(f"Integrity:            {integrity}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Import an Anthropic Claude data export into the existing "
            "WyrmMango SQLite archive."
        )
    )
    parser.add_argument(
        "source",
        help="Path to a Claude export ZIP or extracted export directory.",
    )
    parser.add_argument(
        "--database",
        default=str(DEFAULT_DB),
        help="SQLite database path. Defaults to data/chatarchive.sqlite.",
    )
    parser.add_argument(
        "--no-fts",
        action="store_true",
        help="Skip rebuilding the shared FTS5 index after import.",
    )

    args = parser.parse_args()
    source = Path(args.source).expanduser().resolve()
    db_path = Path(args.database).expanduser().resolve()

    if not source.exists():
        print(f"ERROR: Source does not exist: {source}", file=sys.stderr)
        return 1

    print("WyrmMango Claude Importer")
    print("=========================")
    print(f"Source:   {source}")
    print(f"Database: {db_path}")
    print()

    conversations, source_file, source_archive = load_source(source)
    expected_messages = sum(
        len(c.get("chat_messages", []))
        for c in conversations
        if isinstance(c.get("chat_messages", []), list)
    )

    print(f"Claude conversations discovered: {len(conversations):,}")
    print(f"Claude messages discovered:      {expected_messages:,}")
    print(f"Archive identity:                {source_archive}")
    print(f"Conversation file:               {source_file}")

    connection = initialize_database(db_path)

    try:
        imported_conversations, imported_messages = import_conversations(
            connection,
            conversations,
            source_file,
            source_archive,
        )

        print()
        print(f"Conversations processed: {imported_conversations:,}")
        print(f"Messages processed:      {imported_messages:,}")

        if not args.no_fts:
            print("Rebuilding shared FTS5 index...")
            fts_count = rebuild_fts(connection)
            print(f"FTS5 indexed messages:   {fts_count:,}")

        verify_import(
            connection,
            len(conversations),
            expected_messages,
        )

    finally:
        connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
