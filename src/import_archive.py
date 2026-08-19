from __future__ import annotations

import argparse
import sys
from pathlib import Path


SUPPORTED_SOURCES = (
    "chatgpt",
    "claude",
    "gmail",
)


def build_provider_argv(
    source_type: str,
    source: Path,
    database: Path,
    source_account: str | None = None,
) -> list[str]:

    source_type = source_type.strip().lower()

    if source_type in (
        "chatgpt",
        "claude",
    ):
        return [
            str(source),
            "--database",
            str(database),
        ]

    if source_type == "gmail":
        account = (
            source_account or ""
        ).strip()

        if not account:
            raise ValueError(
                "Gmail source account is required "
                "to preserve multi-account provenance."
            )

        return [
            "--input",
            str(source),
            "--source-account",
            account,
            "--db",
            str(database),
            "--spam-action",
            "quarantine",
            "--trash-action",
            "include",
        ]

    raise ValueError(
        f"Unsupported source type: {source_type}"
    )


def invoke_provider(
    source_type: str,
    provider_argv: list[str],
) -> int:

    source_type = source_type.strip().lower()

    if source_type == "chatgpt":
        import import_chatgpt as provider
    elif source_type == "claude":
        import import_claude as provider
    elif source_type == "gmail":
        import import_gmail as provider
    else:
        raise ValueError(
            f"Unsupported source type: {source_type}"
        )

    old_argv = sys.argv[:]

    try:
        sys.argv = [
            provider.__name__,
            *provider_argv,
        ]
        result = provider.main()
        return int(result or 0)
    finally:
        sys.argv = old_argv


def self_test() -> int:

    source = Path("sample.zip")
    database = Path("sample.sqlite")

    if build_provider_argv(
        "chatgpt",
        source,
        database,
    ) != [
        "sample.zip",
        "--database",
        "sample.sqlite",
    ]:
        raise RuntimeError(
            "ChatGPT translation failed."
        )

    if build_provider_argv(
        "claude",
        source,
        database,
    ) != [
        "sample.zip",
        "--database",
        "sample.sqlite",
    ]:
        raise RuntimeError(
            "Claude translation failed."
        )

    expected_gmail = [
        "--input",
        "sample.zip",
        "--source-account",
        "person@example.test",
        "--db",
        "sample.sqlite",
        "--spam-action",
        "quarantine",
        "--trash-action",
        "include",
    ]

    if build_provider_argv(
        "gmail",
        source,
        database,
        "person@example.test",
    ) != expected_gmail:
        raise RuntimeError(
            "Gmail translation failed."
        )

    try:
        build_provider_argv(
            "gmail",
            source,
            database,
            "",
        )
    except ValueError:
        pass
    else:
        raise RuntimeError(
            "Gmail missing-account fail-closed test failed."
        )

    print(
        "Unified importer dispatcher self-test: PASS"
    )
    print(
        "ChatGPT contract: PASS"
    )
    print(
        "Claude contract: PASS"
    )
    print(
        "Gmail contract: PASS"
    )
    print(
        "Gmail missing-account gate: PASS"
    )

    return 0


def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Dispatch a local WyrmMango import "
            "to its verified source-specific importer."
        )
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
    )
    parser.add_argument(
        "--source-type",
        choices=SUPPORTED_SOURCES,
    )
    parser.add_argument(
        "--input",
    )
    parser.add_argument(
        "--database",
    )
    parser.add_argument(
        "--source-account",
    )

    args = parser.parse_args()

    if args.self_test:
        return self_test()

    if not args.source_type:
        parser.error(
            "--source-type is required."
        )
    if not args.input:
        parser.error(
            "--input is required."
        )
    if not args.database:
        parser.error(
            "--database is required."
        )

    source = Path(
        args.input
    ).expanduser().resolve()

    database = Path(
        args.database
    ).expanduser().resolve()

    if not source.exists():
        print(
            f"ERROR: Source does not exist: {source}",
            file=sys.stderr,
        )
        return 2

    try:
        provider_argv = build_provider_argv(
            args.source_type,
            source,
            database,
            args.source_account,
        )
    except ValueError as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print(
        "WyrmMango unified import dispatcher"
    )
    print(
        f"Source type: {args.source_type}"
    )

    return invoke_provider(
        args.source_type,
        provider_argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
