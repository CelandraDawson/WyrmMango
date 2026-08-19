from __future__ import annotations

import argparse
import ast
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path


FILES = (
    "app.py",
    "database.py",
    "import_archive.py",
    "import_chatgpt.py",
    "import_claude.py",
    "import_gmail.py",
    "search_archive.py",
)

SELF_DISPATCH_FLAG = "--wyrmmango-importer"


def replace_once(
    text: str,
    old: str,
    new: str,
    label: str,
) -> str:
    count = text.count(old)

    if count != 1:
        raise RuntimeError(
            f"Expected exactly one {label}; found {count}."
        )

    return text.replace(old, new, 1)


def offsets(text: str) -> list[int]:
    result = [0]
    total = 0

    for line in text.splitlines(keepends=True):
        total += len(line)
        result.append(total)

    return result


def replace_node(
    text: str,
    node: ast.AST,
    replacement: str,
) -> str:
    if (
        not hasattr(node, "lineno")
        or not hasattr(node, "end_lineno")
        or node.end_lineno is None
    ):
        raise RuntimeError(
            "AST node is missing source line coordinates."
        )

    source_offsets = offsets(text)

    if not replacement.endswith("\n"):
        replacement += "\n"

    return (
        text[:source_offsets[node.lineno - 1]]
        + replacement
        + text[source_offsets[node.end_lineno]:]
    )


def db_assignment(text: str) -> ast.Assign:
    tree = ast.parse(text)
    found: list[ast.Assign] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue

        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and target.attr == "db_path"
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                found.append(node)

    if len(found) != 1:
        raise RuntimeError(
            "Expected exactly one self.db_path assignment; "
            f"found {len(found)}."
        )

    return found[0]


def importer_start(text: str) -> ast.Expr:
    tree = ast.parse(text)
    found: list[ast.Expr] = []

    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.Expr)
            or not isinstance(node.value, ast.Call)
        ):
            continue

        call = node.value
        func = call.func

        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "start"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "import_process"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "self"
            and len(call.args) >= 2
        ):
            continue

        first = call.args[0]

        if (
            isinstance(first, ast.Attribute)
            and first.attr == "executable"
            and isinstance(first.value, ast.Name)
            and first.value.id == "sys"
        ):
            found.append(node)

    if len(found) != 1:
        raise RuntimeError(
            "Expected exactly one source-mode importer QProcess start; "
            f"found {len(found)}."
        )

    return found[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage",
        required=True,
    )
    parser.add_argument(
        "--project",
    )
    args = parser.parse_args()

    project = (
        Path(args.project).resolve()
        if args.project
        else Path(__file__).resolve().parent
    )

    src = project / "src"
    stage = Path(args.stage).resolve()

    if stage.exists():
        shutil.rmtree(stage)

    (stage / "src").mkdir(parents=True)
    (stage / "assets").mkdir()

    for name in FILES:
        source = src / name

        if not source.exists():
            raise RuntimeError(
                f"Missing release source: {source}"
            )

        shutil.copy2(
            source,
            stage / "src" / name,
        )

    for name in (
        "wyrmmango_icon.png",
        "wyrmmango.ico",
    ):
        source = project / "assets" / name

        if source.exists():
            shutil.copy2(
                source,
                stage / "assets" / name,
            )

    app = stage / "src" / "app.py"

    text = (
        app.read_text(
            encoding="utf-8-sig",
        )
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    old_paths = '''PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMPORTER_PATH = Path(__file__).resolve().parent / "import_archive.py"
ASSET_DIR = PROJECT_ROOT / "assets"
BRAND_ICON = ASSET_DIR / "wyrmmango_icon.png"
'''

    new_paths = '''IS_FROZEN = bool(getattr(sys, "frozen", False))

if IS_FROZEN:
    BUNDLE_ROOT = Path(
        getattr(
            sys,
            "_MEIPASS",
            Path(sys.executable).resolve().parent,
        )
    )
    PROJECT_ROOT = Path(sys.executable).resolve().parent
    IMPORTER_PATH = Path(sys.executable).resolve()
    ASSET_DIR = BUNDLE_ROOT / "assets"

    LOCAL_DATA_ROOT = (
        Path(
            os.environ.get(
                "LOCALAPPDATA",
                str(Path.home()),
            )
        )
        / "WyrmMango"
    )

    RELEASE_DB = (
        LOCAL_DATA_ROOT
        / "data"
        / "chatarchive.sqlite"
    )
else:
    BUNDLE_ROOT = Path(__file__).resolve().parent.parent
    PROJECT_ROOT = BUNDLE_ROOT
    IMPORTER_PATH = Path(__file__).resolve().parent / "import_archive.py"
    ASSET_DIR = PROJECT_ROOT / "assets"
    RELEASE_DB = Path(DEFAULT_DB)

BRAND_ICON = ASSET_DIR / "wyrmmango_icon.png"
'''

    text = replace_once(
        text,
        old_paths,
        new_paths,
        "path configuration block",
    )

    db_node = db_assignment(text)
    db_indent = " " * db_node.col_offset

    db_replacement = (
        db_indent
        + "self.db_path = Path(RELEASE_DB)\n\n"
        + db_indent
        + "if IS_FROZEN:\n"
        + db_indent
        + "    self.db_path.parent.mkdir(\n"
        + db_indent
        + "        parents=True,\n"
        + db_indent
        + "        exist_ok=True,\n"
        + db_indent
        + "    )"
    )

    text = replace_node(
        text,
        db_node,
        db_replacement,
    )

    start_node = importer_start(text)
    start_indent = " " * start_node.col_offset

    start_replacement = (
        start_indent
        + "if IS_FROZEN:\n\n"
        + start_indent
        + "    program = sys.executable\n"
        + start_indent
        + "    arguments = [\n"
        + start_indent
        + '        "--wyrmmango-importer",\n'
        + start_indent
        + "        *arguments[1:],\n"
        + start_indent
        + "    ]\n\n"
        + start_indent
        + "else:\n\n"
        + start_indent
        + "    program = sys.executable\n\n"
        + start_indent
        + "self.import_process.start(\n"
        + start_indent
        + "    program,\n"
        + start_indent
        + "    arguments,\n"
        + start_indent
        + ")"
    )

    text = replace_node(
        text,
        start_node,
        start_replacement,
    )

    old_entry = '''if __name__ == "__main__":
    main()
'''

    new_entry = '''def run_self_importer_mode() -> int:
    from import_archive import main as importer_main

    original_argv = sys.argv[:]

    try:
        sys.argv = [
            "import_archive.py",
            *sys.argv[2:],
        ]
        return int(importer_main() or 0)
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    if (
        len(sys.argv) > 1
        and sys.argv[1] == "--wyrmmango-importer"
    ):
        raise SystemExit(
            run_self_importer_mode()
        )

    main()
'''

    text = replace_once(
        text,
        old_entry,
        new_entry,
        "application entry point",
    )

    required_markers = (
        'IMPORTER_PATH = Path(sys.executable).resolve()',
        '"--wyrmmango-importer"',
        "run_self_importer_mode",
        "from import_archive import main as importer_main",
        "self.import_process.start(",
        "program,",
        "arguments,",
    )

    for marker in required_markers:
        if marker not in text:
            raise RuntimeError(
                "Missing staged self-dispatch marker: "
                + marker
            )

    forbidden_markers = (
        "WyrmMangoImporter.exe",
        "program = str(IMPORTER_PATH)",
    )

    for marker in forbidden_markers:
        if marker in text:
            raise RuntimeError(
                "Blocked child-helper architecture remains in staged app: "
                + marker
            )

    ast.parse(text)
    compile(
        text,
        str(app),
        "exec",
    )

    app.write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )

    for path in sorted(
        (stage / "src").glob("*.py")
    ):
        py_compile.compile(
            str(path),
            doraise=True,
        )

    dispatcher = subprocess.run(
        [
            sys.executable,
            str(
                stage
                / "src"
                / "import_archive.py"
            ),
            "--self-test",
        ],
        cwd=str(stage / "src"),
        encoding="utf-8",
        errors="strict",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if dispatcher.returncode != 0:
        raise RuntimeError(
            "Dispatcher staged self-test failed:\n"
            + dispatcher.stdout
            + dispatcher.stderr
        )

    if (
        "Unified importer dispatcher self-test: PASS"
        not in dispatcher.stdout
    ):
        raise RuntimeError(
            "Dispatcher staged self-test output gate failed."
        )

    self_dispatch = subprocess.run(
        [
            sys.executable,
            str(app),
            SELF_DISPATCH_FLAG,
            "--self-test",
        ],
        cwd=str(stage / "src"),
        encoding="utf-8",
        errors="strict",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if self_dispatch.returncode != 0:
        raise RuntimeError(
            "Staged same-executable importer self-dispatch failed:\n"
            + self_dispatch.stdout
            + self_dispatch.stderr
        )

    if (
        "Unified importer dispatcher self-test: PASS"
        not in self_dispatch.stdout
    ):
        raise RuntimeError(
            "Staged self-dispatch output gate failed."
        )

    print(
        "WyrmMango staged Windows release preparation: PASS"
    )
    print(
        f"Stage: {stage}"
    )
    print(
        "Frozen per-user database wiring: PASS"
    )
    print(
        "Same-executable importer dispatch wiring: PASS"
    )
    print(
        "Separate embedded helper executable: REMOVED"
    )
    print(
        "Staged Python compile: PASS"
    )
    print(
        "Dispatcher staged self-test: PASS"
    )
    print(
        "Staged same-executable importer self-test: PASS"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
