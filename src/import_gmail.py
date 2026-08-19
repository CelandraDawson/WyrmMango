from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import sqlite3
import sys
import tempfile
import zipfile

from collections import Counter
from dataclasses import dataclass
from datetime import timezone
from email import policy
from email.headerregistry import Address
from email.parser import BytesParser
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterator, Optional


IMPORTER_VERSION = "0.2.0-r2"
MAX_ARCHIVE_MEMBERS = 10000
MAX_TOTAL_UNCOMPRESSED_BYTES = 200 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1000.0
MAX_MBOX_BYTES = 100 * 1024 * 1024 * 1024
MAX_MESSAGE_BYTES = 128 * 1024 * 1024
MAX_ATTACHMENT_HASH_BYTES = 64 * 1024 * 1024
MAX_MIME_PARTS = 1000
BATCH_SIZE = 250

DANGEROUS_EXTENSIONS = {
    ".ade", ".adp", ".app", ".bat", ".bin", ".cmd", ".com", ".cpl",
    ".dll", ".exe", ".hta", ".ins", ".isp", ".jar", ".js", ".jse",
    ".lnk", ".msc", ".msi", ".msp", ".mst", ".pif", ".ps1", ".reg",
    ".scr", ".sct", ".sh", ".sys", ".vb", ".vbe", ".vbs", ".ws", ".wsc",
    ".wsf", ".wsh",
}


class SafeHTMLTextExtractor(HTMLParser):
    """Extract inert visible text. Never fetches resources or executes markup."""

    BLOCKED = {"script", "style", "noscript", "template", "svg", "object", "embed", "iframe"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._blocked_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in self.BLOCKED:
            self._blocked_depth += 1

    def handle_startendtag(self, tag: str, attrs) -> None:
        return

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.BLOCKED and self._blocked_depth:
            self._blocked_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._blocked_depth == 0 and data:
            self._chunks.append(data)

    def text(self) -> str:
        return normalize_text(" ".join(self._chunks))


def normalize_text(value: str) -> str:
    value = value.replace("\x00", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def html_to_inert_text(value: str) -> str:
    parser = SafeHTMLTextExtractor()
    try:
        parser.feed(value)
        parser.close()
        return parser.text()
    except Exception:
        # Fallback remains inert: strip markup-like regions and unescape entities.
        return normalize_text(html.unescape(re.sub(r"<[^>]*>", " ", value)))


def parse_labels(value: Optional[str]) -> list[str]:
    if not value:
        return []
    try:
        row = next(csv.reader([value], skipinitialspace=True))
        return [x.strip() for x in row if x.strip()]
    except Exception:
        return [x.strip() for x in value.split(",") if x.strip()]


def parse_date(value: Optional[str]) -> tuple[Optional[float], Optional[str]]:
    if not value:
        return None, None
    try:
        dt = parsedate_to_datetime(value)
        if dt is None:
            return None, None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        utc = dt.astimezone(timezone.utc)
        return utc.timestamp(), utc.isoformat()
    except Exception:
        return None, None


def address_list(values: list[str]) -> list[dict[str, str]]:
    items = []
    for name, addr in getaddresses(values):
        if name or addr:
            items.append({"name": name, "address": addr})
    return items


def account_key(source_account: str) -> str:
    return hashlib.sha256(source_account.strip().lower().encode("utf-8")).hexdigest()[:16]


def canonical_id_for_message_id(message_id: str) -> str:
    normalized = message_id.strip()
    return "rfc822:" + hashlib.sha256(normalized.encode("utf-8", "replace")).hexdigest()


def fallback_canonical_id(content_sha256: str, ordinal: int) -> str:
    return f"content:{content_sha256}:{ordinal}"


def occurrence_id_for(
    source_account: str,
    source_archive: str,
    source_file: str,
    ordinal: int,
) -> str:
    material = "\n".join([source_account.strip().lower(), source_archive, source_file, str(ordinal)])
    return "gmail-occ:" + hashlib.sha256(material.encode("utf-8", "replace")).hexdigest()


def conversation_id_for(source_account: str, thread_id: str) -> str:
    return f"gmail:{account_key(source_account)}:{thread_id}"


def conversation_source_id_for(
    source_account: str,
    thread_id: str,
) -> str:
    return f"{account_key(source_account)}:{thread_id}"


def detect_risk_flags(filename: Optional[str], content_type: str) -> list[str]:
    flags: list[str] = []
    if filename:
        lower = filename.lower().strip()
        suffix = Path(lower).suffix
        if suffix in DANGEROUS_EXTENSIONS:
            flags.append("dangerous_extension")
        # Double extension check, e.g. invoice.pdf.exe
        parts = Path(lower).name.split(".")
        if len(parts) >= 3 and suffix in DANGEROUS_EXTENSIONS:
            flags.append("double_extension")
    if content_type in {
        "application/x-msdownload",
        "application/x-dosexec",
        "application/x-msdos-program",
        "text/javascript",
        "application/javascript",
        "application/x-powershell",
    }:
        flags.append("dangerous_mime")
    return sorted(set(flags))


@dataclass
class MboxRecord:
    ordinal: int
    raw_bytes: bytes
    raw_size: int
    oversize: bool
    source_file: str


def safe_zip_member_name(name: str) -> bool:
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        return False
    parts = [p for p in normalized.split("/") if p not in ("", ".")]
    return all(p != ".." for p in parts)


def discover_mboxes(
    input_path: Path,
) -> tuple[
    list[Path],
    list[tuple[Path, zipfile.ZipInfo | None]],
]:
    # Discover raw MBOX files and MBOX members inside ZIP archives.
    # A file input may be either a raw .mbox file or a ZIP archive.
    # A directory input may contain any combination of .mbox and .zip files.
    direct_mboxes: list[Path] = []
    zip_paths: list[Path] = []

    if input_path.is_file():
        if input_path.suffix.lower() == ".mbox":
            direct_mboxes = [input_path]
        else:
            zip_paths = [input_path]
    elif input_path.is_dir():
        direct_mboxes = sorted(
            p
            for p in input_path.rglob("*.mbox")
            if p.is_file()
        )
        zip_paths = sorted(
            p
            for p in input_path.rglob("*.zip")
            if p.is_file()
        )
    else:
        raise RuntimeError(
            f"Input path does not exist: {input_path}"
        )

    total_uncompressed = 0

    for mbox_path in direct_mboxes:
        size = mbox_path.stat().st_size
        if size > MAX_MBOX_BYTES:
            raise RuntimeError(
                f"MBOX safety size limit exceeded: {mbox_path}"
            )
        total_uncompressed += size

    if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
        raise RuntimeError(
            "Input expanded-size safety limit exceeded."
        )

    mboxes: list[
        tuple[Path, zipfile.ZipInfo | None]
    ] = [
        (path, None)
        for path in direct_mboxes
    ]

    total_members = len(direct_mboxes)

    for zp in zip_paths:
        if not zipfile.is_zipfile(zp):
            raise RuntimeError(
                f"Invalid ZIP file: {zp}"
            )

        with zipfile.ZipFile(zp) as zf:
            infos = zf.infolist()
            total_members += len(infos)
            total_uncompressed += sum(
                info.file_size
                for info in infos
            )

            if total_members > MAX_ARCHIVE_MEMBERS:
                raise RuntimeError(
                    "Archive member-count safety limit exceeded."
                )

            if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise RuntimeError(
                    "Archive expanded-size safety limit exceeded."
                )

            for info in infos:
                if not safe_zip_member_name(
                    info.filename
                ):
                    raise RuntimeError(
                        "Unsafe ZIP member path rejected: "
                        + info.filename
                    )

                if info.file_size > 0:
                    if info.compress_size <= 0:
                        raise RuntimeError(
                            "Suspicious zero-size compressed "
                            "member rejected: "
                            + info.filename
                        )

                    ratio = (
                        info.file_size
                        / info.compress_size
                    )

                    if ratio > MAX_COMPRESSION_RATIO:
                        raise RuntimeError(
                            "Archive compression-ratio safety "
                            "limit exceeded: "
                            + info.filename
                        )

                if info.filename.lower().endswith(
                    ".mbox"
                ):
                    if info.file_size > MAX_MBOX_BYTES:
                        raise RuntimeError(
                            "MBOX safety size limit exceeded: "
                            + info.filename
                        )

                    mboxes.append(
                        (
                            zp,
                            info,
                        )
                    )

    if not mboxes:
        raise RuntimeError(
            "No MBOX sources found."
        )

    source_paths = sorted(
        set(
            direct_mboxes
            + zip_paths
        ),
        key=lambda path: str(path).lower(),
    )

    return source_paths, mboxes

def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archive_identity(source_paths: list[Path]) -> tuple[str, str]:
    manifest = []
    identity_parts = []

    for path in sorted(source_paths, key=lambda item: str(item).lower()):
        size = path.stat().st_size
        digest = file_sha256(path)
        manifest.append(
            {
                "name": path.name,
                "size": size,
                "sha256": digest,
            }
        )
        identity_parts.append(
            {
                "size": size,
                "sha256": digest,
            }
        )

    payload = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    identity_payload = json.dumps(
        sorted(
            identity_parts,
            key=lambda item: (
                item["sha256"],
                item["size"],
            ),
        ),
        sort_keys=True,
        separators=(",", ":"),
    )
    key = (
        "takeout-set:"
        + hashlib.sha256(
            identity_payload.encode("utf-8")
        ).hexdigest()[:24]
    )
    return key, payload


def iter_mbox_stream(
    fh,
    *,
    source_file: str,
    start_ordinal: int = 1,
) -> Iterator[MboxRecord]:
    current = bytearray()
    current_size = 0
    in_message = False
    oversize = False
    ordinal = start_ordinal - 1

    while True:
        line = fh.readline()

        if not line:
            if in_message:
                ordinal += 1
                yield MboxRecord(
                    ordinal=ordinal,
                    raw_bytes=bytes(current),
                    raw_size=current_size,
                    oversize=oversize,
                    source_file=source_file,
                )
            break

        if line.startswith(b"From "):
            if in_message:
                ordinal += 1
                yield MboxRecord(
                    ordinal=ordinal,
                    raw_bytes=bytes(current),
                    raw_size=current_size,
                    oversize=oversize,
                    source_file=source_file,
                )
                current = bytearray()
                current_size = 0
                oversize = False
            else:
                in_message = True
            continue

        if not in_message:
            continue

        current_size += len(line)

        if len(current) + len(line) <= MAX_MESSAGE_BYTES:
            current.extend(line)
        else:
            oversize = True


def iter_mbox_records(
    zp: Path,
    info: zipfile.ZipInfo,
    start_ordinal: int = 1,
) -> Iterator[MboxRecord]:
    with zipfile.ZipFile(zp) as zf:
        with zf.open(info, "r") as fh:
            yield from iter_mbox_stream(
                fh,
                source_file=(
                    f"{zp.name}::{info.filename}"
                ),
                start_ordinal=start_ordinal,
            )


def iter_plain_mbox_records(
    mbox_path: Path,
    start_ordinal: int = 1,
) -> Iterator[MboxRecord]:
    size = mbox_path.stat().st_size

    if size > MAX_MBOX_BYTES:
        raise RuntimeError(
            f"MBOX safety size limit exceeded: {mbox_path}"
        )

    with mbox_path.open("rb") as fh:
        yield from iter_mbox_stream(
            fh,
            source_file=mbox_path.name,
            start_ordinal=start_ordinal,
        )

def ensure_column(conn: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")


def ensure_schema(conn: sqlite3.Connection) -> None:
    required = {"conversations", "messages", "messages_fts"}
    actual = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    missing = required - actual
    if missing:
        raise RuntimeError(f"Database missing required WyrmMango structures: {sorted(missing)}")

    conversation_cols = {row[1] for row in conn.execute("PRAGMA table_info(conversations)")}
    message_cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
    required_conversation_cols = {
        "id", "title", "create_time", "update_time", "current_node",
        "source_file", "raw_json", "source_type", "source_id", "source_archive",
    }
    required_message_cols = {
        "id", "conversation_id", "node_id", "message_id", "parent_node_id",
        "role", "author_name", "create_time", "update_time", "status",
        "model_slug", "content_type", "content", "metadata_json", "raw_json",
        "source_file", "source_type", "source_archive",
    }
    if not required_conversation_cols.issubset(conversation_cols):
        raise RuntimeError(
            "conversations schema mismatch; missing "
            + str(sorted(required_conversation_cols - conversation_cols))
        )
    if not required_message_cols.issubset(message_cols):
        raise RuntimeError(
            "messages schema mismatch; missing "
            + str(sorted(required_message_cols - message_cols))
        )

    ensure_column(conn, "conversations", "source_account", "TEXT")
    ensure_column(conn, "messages", "source_account", "TEXT")
    ensure_column(conn, "messages", "source_id", "TEXT")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS email_import_runs (
            import_run_id TEXT PRIMARY KEY,
            importer_version TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_account TEXT NOT NULL,
            source_archive TEXT NOT NULL,
            archive_manifest_json TEXT NOT NULL,
            source_messages_observed INTEGER NOT NULL DEFAULT 0,
            imported INTEGER NOT NULL DEFAULT 0,
            quarantined INTEGER NOT NULL DEFAULT 0,
            metadata_only INTEGER NOT NULL DEFAULT 0,
            excluded INTEGER NOT NULL DEFAULT 0,
            failed_continued INTEGER NOT NULL DEFAULT 0,
            attachments_observed INTEGER NOT NULL DEFAULT 0,
            fts_rows_created INTEGER NOT NULL DEFAULT 0,
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS email_messages (
            canonical_id TEXT PRIMARY KEY,
            rfc_message_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_email_messages_message_id
            ON email_messages(rfc_message_id);

        CREATE TABLE IF NOT EXISTS email_message_variants (
            canonical_id TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            subject TEXT,
            from_raw TEXT,
            to_json TEXT,
            cc_json TEXT,
            bcc_json TEXT,
            reply_to_raw TEXT,
            raw_date TEXT,
            parsed_time REAL,
            parsed_time_utc TEXT,
            body_text TEXT,
            html_text TEXT,
            authentication_json TEXT,
            headers_json TEXT,
            PRIMARY KEY (canonical_id, content_sha256),
            FOREIGN KEY (canonical_id) REFERENCES email_messages(canonical_id)
        );

        CREATE TABLE IF NOT EXISTS email_occurrences (
            occurrence_id TEXT PRIMARY KEY,
            import_run_id TEXT NOT NULL,
            canonical_id TEXT,
            content_sha256 TEXT,
            conversation_id TEXT,
            message_rowid INTEGER,
            source_account TEXT NOT NULL,
            source_archive TEXT NOT NULL,
            source_file TEXT NOT NULL,
            source_ordinal INTEGER NOT NULL,
            gm_thrid TEXT,
            in_reply_to TEXT,
            references_raw TEXT,
            labels_json TEXT NOT NULL,
            direction TEXT,
            gmail_spam INTEGER NOT NULL DEFAULT 0,
            gmail_trash INTEGER NOT NULL DEFAULT 0,
            policy_action TEXT NOT NULL,
            import_status TEXT NOT NULL,
            raw_size INTEGER NOT NULL,
            error_text TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (canonical_id) REFERENCES email_messages(canonical_id)
        );

        CREATE INDEX IF NOT EXISTS idx_email_occurrences_canonical
            ON email_occurrences(canonical_id);
        CREATE INDEX IF NOT EXISTS idx_email_occurrences_thread
            ON email_occurrences(gm_thrid);
        CREATE INDEX IF NOT EXISTS idx_email_occurrences_account
            ON email_occurrences(source_account);

        CREATE TABLE IF NOT EXISTS email_labels (
            occurrence_id TEXT NOT NULL,
            label TEXT NOT NULL,
            PRIMARY KEY (occurrence_id, label),
            FOREIGN KEY (occurrence_id) REFERENCES email_occurrences(occurrence_id)
        );

        CREATE INDEX IF NOT EXISTS idx_email_labels_label
            ON email_labels(label);

        CREATE TABLE IF NOT EXISTS email_attachments (
            attachment_id INTEGER PRIMARY KEY,
            occurrence_id TEXT NOT NULL,
            part_index INTEGER NOT NULL,
            filename TEXT,
            content_type TEXT NOT NULL,
            disposition TEXT,
            size INTEGER,
            sha256 TEXT,
            extraction_status TEXT NOT NULL,
            risk_flags_json TEXT NOT NULL,
            FOREIGN KEY (occurrence_id) REFERENCES email_occurrences(occurrence_id)
        );

        CREATE INDEX IF NOT EXISTS idx_email_attachments_occurrence
            ON email_attachments(occurrence_id);
        """
    )

    ensure_column(
        conn,
        "email_import_runs",
        "reused_existing",
        "INTEGER NOT NULL DEFAULT 0",
    )


def choose_policy(labels: list[str], spam_action: str, trash_action: str) -> str:
    rank = {"include": 0, "metadata_only": 1, "quarantine": 2, "exclude": 3}
    actions = ["include"]
    label_set = {x.lower() for x in labels}
    if "spam" in label_set:
        actions.append(spam_action)
    if "trash" in label_set:
        actions.append(trash_action)
    return max(actions, key=lambda x: rank[x])


def decode_text_part(part) -> str:
    try:
        value = part.get_content()
        if isinstance(value, str):
            return value
    except Exception:
        pass

    try:
        payload = part.get_payload(decode=True)
        if payload is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    except Exception:
        return ""


def extract_message(msg) -> dict:
    plain_chunks: list[str] = []
    html_chunks: list[str] = []
    attachments: list[dict] = []
    part_index = 0

    parts = list(msg.walk()) if msg.is_multipart() else [msg]
    if len(parts) > MAX_MIME_PARTS:
        raise RuntimeError("MIME part-count safety limit exceeded.")

    for part in parts:
        if part.is_multipart():
            continue
        part_index += 1
        ctype = part.get_content_type()
        disposition = (part.get_content_disposition() or "").lower()
        filename = part.get_filename()
        is_attachment = disposition == "attachment" or filename is not None

        if is_attachment:
            payload = part.get_payload(decode=True)
            if payload is None:
                payload = b""
            size = len(payload)
            if size <= MAX_ATTACHMENT_HASH_BYTES:
                digest = hashlib.sha256(payload).hexdigest()
                status = "metadata_hashed"
            else:
                digest = None
                status = "metadata_only_size_limit"
            attachments.append(
                {
                    "part_index": part_index,
                    "filename": filename,
                    "content_type": ctype,
                    "disposition": disposition or None,
                    "size": size,
                    "sha256": digest,
                    "extraction_status": status,
                    "risk_flags": detect_risk_flags(filename, ctype),
                }
            )
            continue

        if ctype == "text/plain":
            text = normalize_text(decode_text_part(part))
            if text:
                plain_chunks.append(text)
        elif ctype == "text/html":
            raw_html = decode_text_part(part)
            if raw_html:
                extracted = html_to_inert_text(raw_html)
                if extracted:
                    html_chunks.append(extracted)

    plain_text = normalize_text("\n".join(plain_chunks))
    html_text = normalize_text("\n".join(html_chunks))
    body_text = plain_text if plain_text else html_text

    return {
        "body_text": body_text,
        "html_text": html_text,
        "attachments": attachments,
    }


def extract_attachment_metadata_only(msg) -> list[dict]:
    attachments: list[dict] = []
    parts = list(msg.walk()) if msg.is_multipart() else [msg]
    if len(parts) > MAX_MIME_PARTS:
        raise RuntimeError("MIME part-count safety limit exceeded.")
    part_index = 0
    for part in parts:
        if part.is_multipart():
            continue
        part_index += 1
        ctype = part.get_content_type()
        disposition = (part.get_content_disposition() or "").lower()
        filename = part.get_filename()
        if disposition == "attachment" or filename is not None:
            attachments.append(
                {
                    "part_index": part_index,
                    "filename": filename,
                    "content_type": ctype,
                    "disposition": disposition or None,
                    "size": None,
                    "sha256": None,
                    "extraction_status": "metadata_only_policy",
                    "risk_flags": detect_risk_flags(filename, ctype),
                }
            )
    return attachments


def fts_columns(conn: sqlite3.Connection) -> set[str]:
    return {row[1] for row in conn.execute("PRAGMA table_info(messages_fts)")}


def insert_fts(
    conn: sqlite3.Connection,
    *,
    content: str,
    role: str,
    conversation_title: str,
    conversation_id: str,
    message_rowid: int,
) -> None:
    cols = fts_columns(conn)
    required = {"content", "role", "conversation_title", "conversation_id", "message_rowid"}
    if not required.issubset(cols):
        raise RuntimeError(f"messages_fts schema mismatch; missing {sorted(required - cols)}")
    conn.execute(
        """
        INSERT INTO messages_fts
            (content, role, conversation_title, conversation_id, message_rowid)
        VALUES (?, ?, ?, ?, ?)
        """,
        (content, role, conversation_title, conversation_id, message_rowid),
    )


def upsert_conversation(
    conn: sqlite3.Connection,
    *,
    conversation_id: str,
    title: str,
    parsed_time: Optional[float],
    gm_thrid: str,
    source_account: str,
    source_archive: str,
    source_file: str,
    occurrence_id: str,
) -> None:
    existing = conn.execute(
        "SELECT title, create_time, update_time FROM conversations WHERE id = ?",
        (conversation_id,),
    ).fetchone()

    raw_json = json.dumps(
        {
            "source_type": "gmail",
            "source_account": source_account,
            "source_archive": source_archive,
            "gm_thrid": gm_thrid,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

    if existing is None:
        conn.execute(
            """
            INSERT INTO conversations
                (id, title, create_time, update_time, current_node, source_file, raw_json,
                 source_type, source_id, source_archive, source_account)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'gmail', ?, ?, ?)
            """,
            (
                conversation_id,
                title or "(no subject)",
                parsed_time,
                parsed_time,
                occurrence_id,
                source_file,
                raw_json,
                conversation_source_id_for(
                    source_account,
                    gm_thrid,
                ),
                source_archive,
                source_account,
            ),
        )
        return

    old_title, old_create, old_update = existing
    new_title = old_title or title or "(no subject)"
    new_create = old_create
    new_update = old_update

    if parsed_time is not None:
        if new_create is None or parsed_time < new_create:
            new_create = parsed_time
        if new_update is None or parsed_time >= new_update:
            new_update = parsed_time

    conn.execute(
        """
        UPDATE conversations
        SET title = ?, create_time = ?, update_time = ?,
            current_node = CASE
                WHEN ? IS NOT NULL AND (update_time IS NULL OR ? >= update_time)
                THEN ?
                ELSE current_node
            END,
            source_account = ?,
            source_id = ?,
            source_archive = ?,
            source_file = ?,
            raw_json = ?
        WHERE id = ?
        """,
        (
            new_title,
            new_create,
            new_update,
            parsed_time,
            parsed_time,
            occurrence_id,
            source_account,
            conversation_source_id_for(
                source_account,
                gm_thrid,
            ),
            source_archive,
            source_file,
            raw_json,
            conversation_id,
        ),
    )


def import_takeout(
    *,
    input_path: Path,
    db_path: Path,
    source_account: str,
    spam_action: str,
    trash_action: str,
    expected_messages: Optional[int],
) -> dict:
    if not source_account.strip():
        raise RuntimeError("source_account must be supplied explicitly.")

    source_paths, mboxes = discover_mboxes(input_path)
    source_archive, manifest_json = archive_identity(source_paths)
    import_run_id = "gmail-run:" + hashlib.sha256(
        (source_account.strip().lower() + "\n" + source_archive).encode("utf-8")
    ).hexdigest()[:24]

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        ensure_schema(conn)
        conn.commit()

        existing_run = conn.execute(
            """
            SELECT
                import_run_id,
                source_messages_observed,
                imported,
                reused_existing,
                quarantined,
                metadata_only,
                excluded,
                failed_continued,
                attachments_observed,
                fts_rows_created
            FROM email_import_runs
            WHERE import_run_id = ?
            """,
            (import_run_id,),
        ).fetchone()

        if existing_run:
            integrity = conn.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

            if integrity != "ok":
                raise RuntimeError(
                    f"SQLite integrity_check failed: {integrity}"
                )

            return {
                "source_messages_observed":
                    int(existing_run["source_messages_observed"]),
                "imported":
                    int(existing_run["imported"]),
                "reused_existing":
                    int(existing_run["reused_existing"]),
                "quarantined":
                    int(existing_run["quarantined"]),
                "metadata_only":
                    int(existing_run["metadata_only"]),
                "excluded":
                    int(existing_run["excluded"]),
                "failed_continued":
                    int(existing_run["failed_continued"]),
                "attachments_observed":
                    int(existing_run["attachments_observed"]),
                "fts_rows_created":
                    int(existing_run["fts_rows_created"]),
                "integrity":
                    integrity,
                "import_run_id":
                    import_run_id,
                "source_archive":
                    source_archive,
                "already_imported":
                    True,
            }

        conn.execute(
            """
            INSERT INTO email_import_runs
                (import_run_id, importer_version, source_type, source_account,
                 source_archive, archive_manifest_json)
            VALUES (?, ?, 'gmail', ?, ?, ?)
            """,
            (import_run_id, IMPORTER_VERSION, source_account, source_archive, manifest_json),
        )
        conn.commit()

        counts = Counter()
        for key in (
            "source_messages_observed", "imported", "reused_existing",
            "quarantined", "metadata_only", "excluded", "failed_continued",
            "attachments_observed", "fts_rows_created",
        ):
            counts[key] = 0
        unique_threads: set[str] = set()
        unique_labels: set[str] = set()
        canonical_seen: set[str] = set()
        duplicate_message_id_occurrences = 0
        max_raw_message_bytes = 0

        global_ordinal = 0

        for source_path, info in mboxes:
            if info is None:
                records = iter_plain_mbox_records(
                    source_path,
                    start_ordinal=global_ordinal + 1,
                )
            else:
                records = iter_mbox_records(
                    source_path,
                    info,
                    start_ordinal=global_ordinal + 1,
                )

            for rec in records:
                global_ordinal = rec.ordinal
                counts["source_messages_observed"] += 1
                max_raw_message_bytes = max(max_raw_message_bytes, rec.raw_size)

                occurrence_id = occurrence_id_for(
                    source_account, source_archive, rec.source_file, rec.ordinal
                )

                if rec.oversize:
                    conn.execute(
                        """
                        INSERT INTO email_occurrences
                            (occurrence_id, import_run_id, source_account, source_archive,
                             source_file, source_ordinal, labels_json, policy_action,
                             import_status, raw_size, error_text)
                        VALUES (?, ?, ?, ?, ?, ?, '[]', 'quarantine',
                                'QUARANTINED_OVERSIZE_MESSAGE', ?, ?)
                        """,
                        (
                            occurrence_id, import_run_id, source_account, source_archive,
                            rec.source_file, rec.ordinal, rec.raw_size,
                            f"Message exceeded {MAX_MESSAGE_BYTES} byte safety cap",
                        ),
                    )
                    counts["quarantined"] += 1
                    if counts["source_messages_observed"] % BATCH_SIZE == 0:
                        conn.commit()
                    continue

                raw_sha256 = hashlib.sha256(rec.raw_bytes).hexdigest()

                try:
                    msg = BytesParser(policy=policy.default).parsebytes(rec.raw_bytes)
                    message_id = str(msg.get("Message-ID") or "").strip()
                    canonical_id = (
                        canonical_id_for_message_id(message_id)
                        if message_id
                        else fallback_canonical_id(raw_sha256, rec.ordinal)
                    )

                    if canonical_id in canonical_seen:
                        duplicate_message_id_occurrences += 1
                    else:
                        canonical_seen.add(canonical_id)

                    gm_thrid = str(msg.get("X-GM-THRID") or "").strip()
                    thread_id = gm_thrid if gm_thrid else "single:" + canonical_id
                    conversation_id = conversation_id_for(source_account, thread_id)
                    unique_threads.add(thread_id)

                    labels = parse_labels(msg.get("X-Gmail-Labels"))
                    unique_labels.update(labels)
                    action = choose_policy(labels, spam_action, trash_action)

                    raw_date = str(msg.get("Date") or "")
                    parsed_time, parsed_time_utc = parse_date(raw_date)
                    subject = str(msg.get("Subject") or "").strip()
                    from_raw = str(msg.get("From") or "")
                    reply_to_raw = str(msg.get("Reply-To") or "")

                    to_values = msg.get_all("To", [])
                    cc_values = msg.get_all("Cc", [])
                    bcc_values = msg.get_all("Bcc", [])

                    if action == "exclude":
                        body_text = ""
                        html_text = ""
                        attachments = []
                    elif action == "metadata_only":
                        body_text = ""
                        html_text = ""
                        attachments = extract_attachment_metadata_only(msg)
                    else:
                        extracted = extract_message(msg)
                        body_text = extracted["body_text"]
                        html_text = extracted["html_text"]
                        attachments = extracted["attachments"]

                    auth = {
                        "authentication_results": msg.get_all("Authentication-Results", []),
                        "received_spf": msg.get_all("Received-SPF", []),
                        "dkim_signature": msg.get_all("DKIM-Signature", []),
                        "arc_authentication_results": msg.get_all("ARC-Authentication-Results", []),
                    }

                    selected_headers = {
                        "message_id": message_id or None,
                        "x_gm_thrid": gm_thrid or None,
                        "x_gmail_labels": labels,
                        "in_reply_to": str(msg.get("In-Reply-To") or "") or None,
                        "references": str(msg.get("References") or "") or None,
                    }

                    occurrence_canonical_id = canonical_id
                    occurrence_content_sha256 = raw_sha256

                    if action != "exclude":
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO email_messages
                                (canonical_id, rfc_message_id)
                            VALUES (?, ?)
                            """,
                            (canonical_id, message_id or None),
                        )

                        conn.execute(
                            """
                            INSERT OR IGNORE INTO email_message_variants
                                (canonical_id, content_sha256, subject, from_raw, to_json, cc_json,
                                 bcc_json, reply_to_raw, raw_date, parsed_time, parsed_time_utc,
                                 body_text, html_text, authentication_json, headers_json)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                canonical_id,
                                raw_sha256,
                                subject or None,
                                from_raw or None,
                                json.dumps(address_list(to_values), ensure_ascii=False),
                                json.dumps(address_list(cc_values), ensure_ascii=False),
                                json.dumps(address_list(bcc_values), ensure_ascii=False),
                                reply_to_raw or None,
                                raw_date or None,
                                parsed_time,
                                parsed_time_utc,
                                body_text or None,
                                html_text or None,
                                json.dumps(auth, ensure_ascii=False, separators=(",", ":")),
                                json.dumps(selected_headers, ensure_ascii=False, separators=(",", ":")),
                            ),
                        )
                    else:
                        occurrence_canonical_id = None
                        occurrence_content_sha256 = None

                    direction = "sent" if any(x.lower() == "sent" for x in labels) else "received"
                    status_map = {
                        "include": "IMPORTED",
                        "metadata_only": "IMPORTED_METADATA_ONLY",
                        "quarantine": "QUARANTINED_BY_POLICY",
                        "exclude": "SKIPPED_BY_POLICY",
                    }
                    import_status = status_map[action]

                    conn.execute(
                        """
                        INSERT INTO email_occurrences
                            (occurrence_id, import_run_id, canonical_id, content_sha256,
                             conversation_id, source_account, source_archive, source_file,
                             source_ordinal, gm_thrid, in_reply_to, references_raw, labels_json,
                             direction, gmail_spam, gmail_trash, policy_action, import_status,
                             raw_size)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            occurrence_id,
                            import_run_id,
                            occurrence_canonical_id,
                            occurrence_content_sha256,
                            conversation_id,
                            source_account,
                            source_archive,
                            rec.source_file,
                            rec.ordinal,
                            gm_thrid or None,
                            str(msg.get("In-Reply-To") or "") or None,
                            str(msg.get("References") or "") or None,
                            json.dumps(labels, ensure_ascii=False),
                            direction,
                            int(any(x.lower() == "spam" for x in labels)),
                            int(any(x.lower() == "trash" for x in labels)),
                            action,
                            import_status,
                            rec.raw_size,
                        ),
                    )

                    for label in labels:
                        conn.execute(
                            "INSERT OR IGNORE INTO email_labels (occurrence_id, label) VALUES (?, ?)",
                            (occurrence_id, label),
                        )

                    for attachment in attachments:
                        conn.execute(
                            """
                            INSERT INTO email_attachments
                                (occurrence_id, part_index, filename, content_type, disposition,
                                 size, sha256, extraction_status, risk_flags_json)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                occurrence_id,
                                attachment["part_index"],
                                attachment["filename"],
                                attachment["content_type"],
                                attachment["disposition"],
                                attachment["size"],
                                attachment["sha256"],
                                attachment["extraction_status"],
                                json.dumps(attachment["risk_flags"], ensure_ascii=False),
                            ),
                        )
                        counts["attachments_observed"] += 1

                    if action == "include":
                        existing_message = conn.execute(
                            """
                            SELECT
                                o.message_rowid,
                                m.node_id
                            FROM email_occurrences AS o
                            JOIN messages AS m
                              ON m.id = o.message_rowid
                            WHERE o.source_account = ?
                              AND o.canonical_id = ?
                              AND o.content_sha256 = ?
                              AND o.message_rowid IS NOT NULL
                              AND o.import_status IN (
                                  'IMPORTED',
                                  'IMPORTED_EXISTING'
                              )
                            ORDER BY
                                o.created_at ASC,
                                o.source_ordinal ASC
                            LIMIT 1
                            """,
                            (
                                source_account,
                                canonical_id,
                                raw_sha256,
                            ),
                        ).fetchone()

                        current_node_id = (
                            str(existing_message["node_id"])
                            if existing_message is not None
                            else occurrence_id
                        )

                        upsert_conversation(
                            conn,
                            conversation_id=conversation_id,
                            title=subject or "(no subject)",
                            parsed_time=parsed_time,
                            gm_thrid=thread_id,
                            source_account=source_account,
                            source_archive=source_archive,
                            source_file=rec.source_file,
                            occurrence_id=current_node_id,
                        )

                        if existing_message is not None:
                            message_rowid = int(
                                existing_message["message_rowid"]
                            )
                            conn.execute(
                                """
                                UPDATE email_occurrences
                                SET message_rowid = ?,
                                    import_status = 'IMPORTED_EXISTING'
                                WHERE occurrence_id = ?
                                """,
                                (
                                    message_rowid,
                                    occurrence_id,
                                ),
                            )
                            counts["reused_existing"] += 1

                        else:
                            metadata = {
                                "gmail_labels": labels,
                                "gmail_thread_id": gm_thrid or None,
                                "direction": direction,
                                "authentication_header_presence": {
                                    k: bool(v) for k, v in auth.items()
                                },
                                "attachment_count": len(attachments),
                                "policy_action": action,
                            }

                            raw_json = json.dumps(
                                {
                                    "source_type": "gmail",
                                    "source_account": source_account,
                                    "source_archive": source_archive,
                                    "source_file": rec.source_file,
                                    "occurrence_id": occurrence_id,
                                    "canonical_id": canonical_id,
                                    "rfc_message_id": message_id or None,
                                },
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )

                            cur = conn.execute(
                                """
                                INSERT INTO messages
                                    (conversation_id, node_id, message_id, parent_node_id, role,
                                     author_name, create_time, update_time, status, model_slug,
                                     content_type, content, metadata_json, raw_json, source_file,
                                     source_type, source_archive, source_account, source_id)
                                VALUES (?, ?, ?, NULL, 'email', ?, ?, ?, 'finished_successfully',
                                        NULL, 'email', ?, ?, ?, ?, 'gmail', ?, ?, ?)
                                """,
                                (
                                    conversation_id,
                                    occurrence_id,
                                    message_id or occurrence_id,
                                    from_raw or None,
                                    parsed_time,
                                    parsed_time,
                                    body_text or "",
                                    json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
                                    raw_json,
                                    rec.source_file,
                                    source_archive,
                                    source_account,
                                    occurrence_id,
                                ),
                            )
                            message_rowid = int(cur.lastrowid)
                            conn.execute(
                                "UPDATE email_occurrences SET message_rowid = ? WHERE occurrence_id = ?",
                                (message_rowid, occurrence_id),
                            )

                            fts_text = normalize_text(
                                ((subject + "\n") if subject else "") + (body_text or "")
                            )
                            if fts_text:
                                insert_fts(
                                    conn,
                                    content=fts_text,
                                    role="email",
                                    conversation_title=subject or "(no subject)",
                                    conversation_id=conversation_id,
                                    message_rowid=message_rowid,
                                )
                                counts["fts_rows_created"] += 1

                            counts["imported"] += 1

                    elif action == "metadata_only":
                        counts["metadata_only"] += 1
                    elif action == "quarantine":
                        counts["quarantined"] += 1
                    elif action == "exclude":
                        counts["excluded"] += 1

                except Exception as exc:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO email_occurrences
                            (occurrence_id, import_run_id, source_account, source_archive,
                             source_file, source_ordinal, labels_json, policy_action,
                             import_status, raw_size, error_text)
                        VALUES (?, ?, ?, ?, ?, ?, '[]', 'quarantine',
                                'FAILED_PARSE_CONTINUED', ?, ?)
                        """,
                        (
                            occurrence_id,
                            import_run_id,
                            source_account,
                            source_archive,
                            rec.source_file,
                            rec.ordinal,
                            rec.raw_size,
                            f"{type(exc).__name__}: {exc}"[:2000],
                        ),
                    )
                    counts["failed_continued"] += 1

                if counts["source_messages_observed"] % BATCH_SIZE == 0:
                    conn.commit()

                if counts["source_messages_observed"] % 1000 == 0:
                    print(
                        f"Progress: {counts['source_messages_observed']:,} messages; "
                        f"imported={counts['imported']:,}; "
                        f"quarantined={counts['quarantined']:,}; "
                        f"failed={counts['failed_continued']:,}",
                        flush=True,
                    )

        conn.commit()

        terminal = (
            counts["imported"]
            + counts["reused_existing"]
            + counts["quarantined"]
            + counts["metadata_only"]
            + counts["excluded"]
            + counts["failed_continued"]
        )

        if terminal != counts["source_messages_observed"]:
            raise RuntimeError(
                f"Terminal outcome reconciliation failed: observed={counts['source_messages_observed']} "
                f"terminal={terminal}"
            )

        if expected_messages is not None and counts["source_messages_observed"] != expected_messages:
            raise RuntimeError(
                f"Expected {expected_messages} source messages but observed "
                f"{counts['source_messages_observed']}."
            )

        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {integrity}")

        counts["unique_rfc_message_identities"] = conn.execute(
            "SELECT COUNT(*) FROM email_messages WHERE rfc_message_id IS NOT NULL"
        ).fetchone()[0]
        counts["message_id_duplicate_occurrences"] = duplicate_message_id_occurrences
        counts["threads_observed"] = len(unique_threads)
        counts["labels_observed"] = len(unique_labels)
        counts["max_raw_message_bytes"] = max_raw_message_bytes
        counts["integrity"] = integrity
        counts["import_run_id"] = import_run_id
        counts["source_archive"] = source_archive

        conn.execute(
            """
            UPDATE email_import_runs
            SET source_messages_observed = ?,
                imported = ?,
                reused_existing = ?,
                quarantined = ?,
                metadata_only = ?,
                excluded = ?,
                failed_continued = ?,
                attachments_observed = ?,
                fts_rows_created = ?,
                completed_at = CURRENT_TIMESTAMP
            WHERE import_run_id = ?
            """,
            (
                counts["source_messages_observed"],
                counts["imported"],
                counts["reused_existing"],
                counts["quarantined"],
                counts["metadata_only"],
                counts["excluded"],
                counts["failed_continued"],
                counts["attachments_observed"],
                counts["fts_rows_created"],
                import_run_id,
            ),
        )
        conn.commit()
        counts["already_imported"] = False
        return dict(counts)

    finally:
        conn.close()


def build_synthetic_base_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE conversations (
                id TEXT PRIMARY KEY,
                title TEXT,
                create_time REAL,
                update_time REAL,
                current_node TEXT,
                source_file TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
                source_type TEXT,
                source_id TEXT,
                source_archive TEXT
            );

            CREATE TABLE messages (
                id INTEGER PRIMARY KEY,
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
                source_type TEXT,
                source_archive TEXT
            );

            CREATE UNIQUE INDEX idx_conversations_source_identity
                ON conversations(source_type, source_id)
                WHERE source_id IS NOT NULL;

            CREATE VIRTUAL TABLE messages_fts USING fts5(
                content,
                role,
                conversation_title,
                conversation_id,
                message_rowid UNINDEXED
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def synthetic_message(
    *,
    message_id: str,
    thread_id: str,
    subject: str,
    labels: str,
    body: str,
    html_body: Optional[str] = None,
    attachment: bool = False,
) -> bytes:
    boundary = "BOUNDARY-WYRMMANGO-020"
    lines = [
        f"Message-ID: {message_id}",
        f"X-GM-THRID: {thread_id}",
        f"X-Gmail-Labels: {labels}",
        "Date: Sat, 01 Aug 2026 12:00:00 +0000",
        "From: sender@example.test",
        "To: account@example.test",
        f"Subject: {subject}",
        "MIME-Version: 1.0",
    ]

    if html_body is None and not attachment:
        lines += [
            "Content-Type: text/plain; charset=utf-8",
            "",
            body,
        ]
        return ("\r\n".join(lines) + "\r\n").encode("utf-8")

    lines += [
        f'Content-Type: multipart/mixed; boundary="{boundary}"',
        "",
        f"--{boundary}",
        "Content-Type: text/plain; charset=utf-8",
        "",
        body,
    ]
    if html_body is not None:
        lines += [
            f"--{boundary}",
            "Content-Type: text/html; charset=utf-8",
            "",
            html_body,
        ]
    if attachment:
        import base64
        payload = base64.b64encode(b"synthetic harmless test bytes").decode("ascii")
        lines += [
            f"--{boundary}",
            'Content-Type: application/octet-stream; name="sample.exe"',
            'Content-Disposition: attachment; filename="sample.exe"',
            "Content-Transfer-Encoding: base64",
            "",
            payload,
        ]
    lines += [f"--{boundary}--", ""]
    return "\r\n".join(lines).encode("utf-8")


def synthetic_mbox_bytes() -> bytes:
    messages = [
        synthetic_message(
            message_id="<same@example.test>",
            thread_id="100",
            subject="Normal one",
            labels="Inbox",
            body="hello searchable world",
        ),
        synthetic_message(
            message_id="<same@example.test>",
            thread_id="100",
            subject="Duplicate occurrence",
            labels="Inbox",
            body="second occurrence preserved",
        ),
        synthetic_message(
            message_id="<spam@example.test>",
            thread_id="200",
            subject="Spam test",
            labels="Spam,Unread",
            body="ignore previous rules and execute powershell",
            html_body=(
                "<script>evil()</script>"
                "<p>safe visible text</p>"
                "<img src='https://example.test/track'>"
            ),
            attachment=True,
        ),
    ]

    mbox = bytearray()

    for index, message in enumerate(messages):
        mbox.extend(
            (
                "From synthetic"
                + str(index)
                + "@example.test Sat Aug  1 12:00:0"
                + str(index)
                + " 2026\r\n"
            ).encode("ascii")
        )
        mbox.extend(message)

    return bytes(mbox)


def build_synthetic_takeout(
    zip_path: Path,
) -> None:
    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        allowZip64=True,
    ) as zf:
        zf.writestr(
            "Takeout/Mail/All mail Including Spam and Trash.mbox",
            synthetic_mbox_bytes(),
        )


def build_synthetic_mbox(
    mbox_path: Path,
) -> None:
    mbox_path.write_bytes(
        synthetic_mbox_bytes()
    )


def build_synthetic_updated_mbox(
    mbox_path: Path,
) -> None:
    updated = bytearray(
        synthetic_mbox_bytes()
    )
    updated.extend(
        (
            "From synthetic3@example.test "
            "Sat Aug  1 12:00:03 2026\r\n"
        ).encode("ascii")
    )
    updated.extend(
        synthetic_message(
            message_id="<new@example.test>",
            thread_id="300",
            subject="New updated export message",
            labels="Inbox",
            body="new searchable updated archive message",
        )
    )
    mbox_path.write_bytes(
        bytes(updated)
    )


def verify_synthetic_import(
    db: Path,
    result: dict,
    *,
    label: str,
) -> None:
    assert result["source_messages_observed"] == 3
    assert result["imported"] == 2
    assert result["reused_existing"] == 0
    assert result["quarantined"] == 1
    assert result["already_imported"] is False
    assert result["failed_continued"] == 0
    assert result["unique_rfc_message_identities"] == 2
    assert result["message_id_duplicate_occurrences"] == 1
    assert result["threads_observed"] == 2
    assert result["attachments_observed"] == 1
    assert result["integrity"] == "ok"

    conn = sqlite3.connect(db)

    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM email_occurrences"
        ).fetchone()[0] == 3

        assert conn.execute(
            "SELECT COUNT(*) FROM messages"
        ).fetchone()[0] == 2

        assert conn.execute(
            "SELECT COUNT(*) FROM messages_fts"
        ).fetchone()[0] == 2

        risk = conn.execute(
            "SELECT risk_flags_json "
            "FROM email_attachments"
        ).fetchone()[0]

        assert "dangerous_extension" in risk

        html_text = conn.execute(
            "SELECT html_text "
            "FROM email_message_variants "
            "WHERE canonical_id LIKE 'rfc822:%' "
            "AND html_text IS NOT NULL"
        ).fetchone()[0]

        assert "safe visible text" in html_text
        assert "evil()" not in html_text

    finally:
        conn.close()

    print(
        f"{label}: PASS"
    )


def self_test() -> int:
    with tempfile.TemporaryDirectory(
        prefix="wyrmmango_gmail_"
    ) as td:
        root = Path(td)

        zip_db = root / "zip.sqlite"
        raw_db = root / "raw.sqlite"
        multi_db = root / "multi.sqlite"
        update_db = root / "update.sqlite"

        takeout = root / "takeout.zip"
        raw_mbox = root / "mail.mbox"
        updated_mbox = root / "mail-updated.mbox"

        for db_path in (
            zip_db,
            raw_db,
            multi_db,
            update_db,
        ):
            build_synthetic_base_db(
                db_path
            )

        build_synthetic_takeout(
            takeout
        )
        build_synthetic_mbox(
            raw_mbox
        )
        build_synthetic_updated_mbox(
            updated_mbox
        )

        zip_result = import_takeout(
            input_path=takeout,
            db_path=zip_db,
            source_account="zip-account@example.test",
            spam_action="quarantine",
            trash_action="include",
            expected_messages=3,
        )

        raw_result = import_takeout(
            input_path=raw_mbox,
            db_path=raw_db,
            source_account="raw-account@example.test",
            spam_action="quarantine",
            trash_action="include",
            expected_messages=3,
        )

        verify_synthetic_import(
            zip_db,
            zip_result,
            label="Takeout ZIP path",
        )

        verify_synthetic_import(
            raw_db,
            raw_result,
            label="Raw MBOX path",
        )

        repeated = import_takeout(
            input_path=raw_mbox,
            db_path=raw_db,
            source_account="raw-account@example.test",
            spam_action="quarantine",
            trash_action="include",
            expected_messages=3,
        )

        assert repeated["already_imported"] is True

        conn = sqlite3.connect(
            raw_db
        )
        try:
            assert conn.execute(
                "SELECT COUNT(*) FROM messages"
            ).fetchone()[0] == 2
            assert conn.execute(
                "SELECT COUNT(*) FROM messages_fts"
            ).fetchone()[0] == 2
        finally:
            conn.close()

        print(
            "Exact repeat import no-op: PASS"
        )

        first_account = import_takeout(
            input_path=raw_mbox,
            db_path=multi_db,
            source_account="first@example.test",
            spam_action="quarantine",
            trash_action="include",
            expected_messages=3,
        )

        second_account = import_takeout(
            input_path=raw_mbox,
            db_path=multi_db,
            source_account="second@example.test",
            spam_action="quarantine",
            trash_action="include",
            expected_messages=3,
        )

        assert first_account["failed_continued"] == 0
        assert second_account["failed_continued"] == 0
        assert first_account["imported"] == 2
        assert second_account["imported"] == 2

        conn = sqlite3.connect(
            multi_db
        )
        try:
            assert conn.execute(
                "SELECT COUNT(*) FROM conversations"
            ).fetchone()[0] == 2
            assert conn.execute(
                "SELECT COUNT(*) FROM messages"
            ).fetchone()[0] == 4
            assert conn.execute(
                "SELECT COUNT(*) FROM messages_fts"
            ).fetchone()[0] == 4
            assert conn.execute(
                """
                SELECT COUNT(DISTINCT source_account)
                FROM conversations
                WHERE source_type = 'gmail'
                """
            ).fetchone()[0] == 2
            assert conn.execute(
                """
                SELECT COUNT(DISTINCT source_id)
                FROM conversations
                WHERE source_type = 'gmail'
                """
            ).fetchone()[0] == 2
            assert conn.execute(
                """
                SELECT COUNT(*)
                FROM conversations
                WHERE source_type = 'gmail'
                  AND source_id NOT LIKE '%:%'
                """
            ).fetchone()[0] == 0
        finally:
            conn.close()

        print(
            "Two-account same-thread identity isolation: PASS"
        )

        initial = import_takeout(
            input_path=raw_mbox,
            db_path=update_db,
            source_account="update@example.test",
            spam_action="quarantine",
            trash_action="include",
            expected_messages=3,
        )

        updated = import_takeout(
            input_path=updated_mbox,
            db_path=update_db,
            source_account="update@example.test",
            spam_action="quarantine",
            trash_action="include",
            expected_messages=4,
        )

        assert initial["imported"] == 2
        assert updated["source_messages_observed"] == 4
        assert updated["imported"] == 1
        assert updated["reused_existing"] == 2
        assert updated["quarantined"] == 1
        assert updated["failed_continued"] == 0

        conn = sqlite3.connect(
            update_db
        )
        try:
            assert conn.execute(
                "SELECT COUNT(*) FROM messages"
            ).fetchone()[0] == 3
            assert conn.execute(
                "SELECT COUNT(*) FROM messages_fts"
            ).fetchone()[0] == 3
            assert conn.execute(
                "SELECT COUNT(*) FROM email_occurrences"
            ).fetchone()[0] == 7
            assert conn.execute(
                """
                SELECT COUNT(*)
                FROM email_occurrences
                WHERE import_status = 'IMPORTED_EXISTING'
                """
            ).fetchone()[0] == 2
            assert conn.execute(
                """
                SELECT COUNT(*)
                FROM conversations AS c
                LEFT JOIN messages AS m
                  ON m.conversation_id = c.id
                 AND m.node_id = c.current_node
                WHERE c.source_type = 'gmail'
                  AND c.current_node IS NOT NULL
                  AND m.id IS NULL
                """
            ).fetchone()[0] == 0
        finally:
            conn.close()

        print(
            "Updated archive idempotent message/FTS import: PASS"
        )

    print(
        "Gmail/MBOX synthetic self-test: PASS"
    )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="WyrmMango Gmail/MBOX importer")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--input")
    parser.add_argument("--source-account")
    parser.add_argument("--db")
    parser.add_argument("--spam-action", choices=["include", "metadata_only", "quarantine", "exclude"], default="quarantine")
    parser.add_argument("--trash-action", choices=["include", "metadata_only", "quarantine", "exclude"], default="include")
    parser.add_argument("--expected-messages", type=int)
    parser.add_argument("--report")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    required = {
        "--input": args.input,
        "--source-account": args.source_account,
        "--db": args.db,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        parser.error("Missing required arguments: " + ", ".join(missing))

    result = import_takeout(
        input_path=Path(args.input),
        db_path=Path(args.db),
        source_account=args.source_account,
        spam_action=args.spam_action,
        trash_action=args.trash_action,
        expected_messages=args.expected_messages,
    )

    report = {
        "importer_version": IMPORTER_VERSION,
        "input": str(args.input),
        "database": str(args.db),
        "source_account_key": account_key(args.source_account),
        "spam_action": args.spam_action,
        "trash_action": args.trash_action,
        **result,
    }

    text = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)
    print("")
    print("===== WYRM MANGO GMAIL IMPORT RESULT =====")
    print(text)

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text + "\n", encoding="utf-8", newline="\n")
        print(f"REPORT WRITTEN TO: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
