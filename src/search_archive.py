from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

from database import DEFAULT_DB


def make_fts_query(
    text: str,
    exact: bool = False,
    raw: bool = False,
) -> str:

    text = text.strip()

    if raw:
        return text

    if exact:
        escaped = text.replace('"', '""')
        return f'"{escaped}"'

    terms = [
        term.strip()
        for term in re.split(r"\s+", text)
        if term.strip()
    ]

    quoted = []

    for term in terms:
        escaped = term.replace('"', '""')
        quoted.append(f'"{escaped}"')

    return " AND ".join(quoted)


def print_stats(connection: sqlite3.Connection) -> None:

    conversations = connection.execute(
        "SELECT COUNT(*) FROM conversations"
    ).fetchone()[0]

    messages = connection.execute(
        "SELECT COUNT(*) FROM messages"
    ).fetchone()[0]

    searchable = connection.execute(
        "SELECT COUNT(*) FROM messages_fts"
    ).fetchone()[0]

    print("ChatArchive Statistics")
    print("======================")
    print(f"Conversations: {conversations:,}")
    print(f"Message nodes: {messages:,}")
    print(f"Searchable:    {searchable:,}")


def search(
    connection: sqlite3.Connection,
    query: str,
    title: str | None,
    role: str | None,
    after: str | None,
    before: str | None,
    model: str | None,
    conversation_id: str | None,
    limit: int,
    exact: bool,
    raw: bool,
    full: bool,
) -> None:

    fts_query = make_fts_query(
        query,
        exact=exact,
        raw=raw,
    )

    sql = """
    SELECT
        m.id,
        m.conversation_id,
        c.title,
        m.role,
        m.author_name,
        m.model_slug,
        m.create_time,
        datetime(
            m.create_time,
            'unixepoch',
            'localtime'
        ) AS local_time,
        m.content,
        m.source_file,
        bm25(messages_fts) AS rank

    FROM messages_fts

    JOIN messages AS m
      ON m.id = messages_fts.message_rowid

    JOIN conversations AS c
      ON c.id = m.conversation_id

    WHERE messages_fts MATCH ?
    """

    params: list[object] = [fts_query]

    if title:
        sql += """
        AND LOWER(COALESCE(c.title, ''))
            LIKE LOWER(?)
        """
        params.append(f"%{title}%")

    if role:
        sql += """
        AND LOWER(COALESCE(m.role, ''))
            = LOWER(?)
        """
        params.append(role)

    if after:
        sql += """
        AND date(
            m.create_time,
            'unixepoch',
            'localtime'
        ) >= date(?)
        """
        params.append(after)

    if before:
        sql += """
        AND date(
            m.create_time,
            'unixepoch',
            'localtime'
        ) <= date(?)
        """
        params.append(before)

    if model:
        sql += """
        AND LOWER(COALESCE(m.model_slug, ''))
            LIKE LOWER(?)
        """
        params.append(f"%{model}%")

    if conversation_id:
        sql += """
        AND m.conversation_id = ?
        """
        params.append(conversation_id)

    sql += """
    ORDER BY
        rank ASC,
        m.create_time ASC

    LIMIT ?
    """

    params.append(limit)

    rows = connection.execute(
        sql,
        params,
    ).fetchall()

    print()
    print(
        f"Search: {query}"
    )

    print(
        f"Results: {len(rows)}"
    )

    print("=" * 72)

    if not rows:
        print("No matching messages found.")
        return

    for number, row in enumerate(
        rows,
        start=1,
    ):

        content = row["content"] or ""

        if not full and len(content) > 800:
            content = content[:800].rstrip() + " ..."

        print()
        print(
            f"[{number}] "
            f"{row['title'] or '(Untitled Conversation)'}"
        )

        print(
            f"Date:  {row['local_time'] or 'Unknown'}"
        )

        print(
            f"Role:  {row['role'] or 'Unknown'}"
        )

        if row["model_slug"]:
            print(
                f"Model: {row['model_slug']}"
            )

        print(
            f"Conversation ID: "
            f"{row['conversation_id']}"
        )

        print(
            f"Message row: "
            f"{row['id']}"
        )

        print(
            f"Source: "
            f"{row['source_file']}"
        )

        print("-" * 72)

        print(content)

        print("=" * 72)


def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Search a local SQLite archive "
            "created from a ChatGPT data export."
        )
    )

    parser.add_argument(
        "query",
        nargs="?",
        help="Words or phrase to search for.",
    )

    parser.add_argument(
        "--title",
        help="Filter by conversation title.",
    )

    parser.add_argument(
        "--role",
        choices=[
            "user",
            "assistant",
            "system",
            "tool",
        ],
        help="Filter by message role.",
    )

    parser.add_argument(
        "--after",
        help="Include messages on/after YYYY-MM-DD.",
    )

    parser.add_argument(
        "--before",
        help="Include messages on/before YYYY-MM-DD.",
    )

    parser.add_argument(
        "--model",
        help="Filter by model name/slug.",
    )

    parser.add_argument(
        "--conversation-id",
        help="Search only one conversation ID.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum results. Default: 20.",
    )

    parser.add_argument(
        "--exact",
        action="store_true",
        help="Search for the exact phrase.",
    )

    parser.add_argument(
        "--raw",
        action="store_true",
        help=(
            "Pass the query directly to SQLite "
            "FTS5 advanced MATCH syntax."
        ),
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Display complete message text.",
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show archive statistics.",
    )

    parser.add_argument(
        "--database",
        default=str(DEFAULT_DB),
        help="Path to SQLite archive database.",
    )

    args = parser.parse_args()

    db_path = Path(
        args.database
    ).expanduser().resolve()

    if not db_path.exists():
        raise SystemExit(
            f"Database not found: {db_path}"
        )

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    try:

        if args.stats:
            print_stats(connection)

            if not args.query:
                return 0

        if not args.query:
            parser.error(
                "Provide a search query or use --stats."
            )

        search(
            connection=connection,
            query=args.query,
            title=args.title,
            role=args.role,
            after=args.after,
            before=args.before,
            model=args.model,
            conversation_id=args.conversation_id,
            limit=args.limit,
            exact=args.exact,
            raw=args.raw,
            full=args.full,
        )

    finally:
        connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
