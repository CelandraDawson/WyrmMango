from __future__ import annotations

import py_compile
import shutil
from pathlib import Path

PROJECT = Path.cwd()
APP = PROJECT / "src" / "app.py"
GITIGNORE = PROJECT / ".gitignore"
BACKUP_DIR = PROJECT / ".release_backup"

if not APP.exists():
    raise SystemExit(
        "ERROR: src/app.py not found.\n"
        "Run this from the root of D:\\WyrmMango-Public."
    )

text = APP.read_text(encoding="utf-8")

def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"ERROR: Expected exactly one {label} block, found {count}. "
            "No file was changed."
        )
    text = text.replace(old, new, 1)

# 1) Add os import.
if "\nimport os\n" not in text:
    replace_once(
        "import html\nimport re\n",
        "import html\nimport os\nimport re\n",
        "import section",
    )

# 2) Make paths work both from source and from a PyInstaller one-file executable.
old_paths = '''PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMPORTER_PATH = Path(__file__).resolve().parent / "import_chatgpt.py"
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
    IMPORTER_PATH = BUNDLE_ROOT / "WyrmMangoImporter.exe"
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
    IMPORTER_PATH = (
        Path(__file__).resolve().parent
        / "import_chatgpt.py"
    )
    ASSET_DIR = PROJECT_ROOT / "assets"
    RELEASE_DB = Path(DEFAULT_DB)

BRAND_ICON = ASSET_DIR / "wyrmmango_icon.png"
'''

if old_paths in text:
    replace_once(old_paths, new_paths, "path configuration")
elif 'IS_FROZEN = bool(getattr(sys, "frozen", False))' not in text:
    raise SystemExit(
        "ERROR: Could not find the expected path configuration block. "
        "No file was changed."
    )

# 3) Use a per-user database path in the packaged application.
old_db = "        self.db_path = Path(DEFAULT_DB)\n"
new_db = '''        self.db_path = Path(RELEASE_DB)

        if IS_FROZEN:
            self.db_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
'''

if old_db in text:
    replace_once(old_db, new_db, "database path")
elif "self.db_path = Path(RELEASE_DB)" not in text:
    raise SystemExit(
        "ERROR: Could not find the expected database assignment. "
        "No file was changed."
    )

# 4) Source mode runs the Python importer script as before.
#    Frozen mode runs the importer executable embedded in WyrmMango.exe.
old_launch = '''        arguments = [
            str(IMPORTER_PATH),
            str(self.selected_export),
            "--database",
            str(self.db_path),
        ]

        self.import_process.start(
            sys.executable,
            arguments,
        )
'''

new_launch = '''        if IS_FROZEN:

            program = str(IMPORTER_PATH)

            arguments = [
                str(self.selected_export),
                "--database",
                str(self.db_path),
            ]

        else:

            program = sys.executable

            arguments = [
                str(IMPORTER_PATH),
                str(self.selected_export),
                "--database",
                str(self.db_path),
            ]

        self.import_process.start(
            program,
            arguments,
        )
'''

if old_launch in text:
    replace_once(old_launch, new_launch, "importer launch")
elif "program = str(IMPORTER_PATH)" not in text:
    raise SystemExit(
        "ERROR: Could not find the expected importer launch block. "
        "No file was changed."
    )

# Validate before touching the working file.
compile(text, str(APP), "exec")

BACKUP_DIR.mkdir(exist_ok=True)
backup = BACKUP_DIR / "app.py.pre_windows_release.bak"
shutil.copy2(APP, backup)

APP.write_text(text, encoding="utf-8", newline="\n")
py_compile.compile(str(APP), doraise=True)

# Ignore build artifacts if not already covered.
if GITIGNORE.exists():
    gi = GITIGNORE.read_text(encoding="utf-8")
else:
    gi = ""

needed = [
    "build/",
    "dist/",
    "release/",
    "*.spec",
    ".release_backup/",
]

lines = gi.splitlines()
missing = [item for item in needed if item not in lines]
if missing:
    with GITIGNORE.open("a", encoding="utf-8", newline="\n") as f:
        if gi and not gi.endswith("\n"):
            f.write("\n")
        f.write("\n# Windows release build artifacts\n")
        for item in missing:
            f.write(item + "\n")

print("WyrmMango Windows release preparation: PASS")
print(f"Backup: {backup}")
print(f"Patched: {APP}")
print("Syntax validation: PASS")
print("Build artifacts added to .gitignore")
