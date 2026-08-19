# WyrmMango

**Dig deep. Find the thread.**

Copyright © 2026 Celandra Dawson

WyrmMango is a private, local-first desktop application for importing, unifying, and searching your own AI conversation and correspondence archives.

WyrmMango 0.2.0 supports ChatGPT, Claude, and Gmail/MBOX sources in one local SQLite archive, so you can answer a simple question across services:

> **Where did I talk about this?**

Your archive stays on your computer. WyrmMango does not require ongoing access to your ChatGPT, Claude, or Gmail accounts after you have obtained your local export files.

## Features

- Import official ChatGPT data export ZIP files
- Import Claude export ZIP files or extracted export directories
- Import Gmail Takeout MBOX files
- Preserve source provenance in one shared local archive
- Search all sources together or filter by source
- Filter Gmail results by source account
- SQLite FTS5 full-text search
- Exact phrase search
- Filter by role, conversation title, and date range where applicable
- Read matched messages and full conversations
- Export search results and conversations to Markdown
- Re-import updated local archives
- Local desktop interface built with PySide6

## Privacy

WyrmMango is designed around local ownership of personal archives.

The public source repository does **not** contain your private conversations, email, local SQLite database, or source export archives.

The following are excluded from Git by default:

- ChatGPT export ZIP files and extracted conversation JSON
- Claude export ZIP files and extracted archive content
- Gmail Takeout archives and MBOX files
- SQLite databases
- extracted attachments and local attachment data
- local archive and import directories
- local environment files
- Python virtual environments
- backup files
- generated release-work directories

Never commit your personal source archives or generated SQLite database to a public repository.

## Supported Sources

### ChatGPT

Use an official ChatGPT data export ZIP. The source-specific ChatGPT importer preserves conversation and message provenance while normalizing content into the shared archive.

### Claude

The desktop application accepts a Claude export ZIP. The source-specific Claude importer also accepts an extracted export directory when run directly from the command line. Claude data is normalized into the same searchable archive.

### Gmail / MBOX

The desktop application accepts either a Google Takeout ZIP containing one or more MBOX files or a raw `.mbox` file. WyrmMango preserves source-account provenance and available mail metadata while importing mail into the shared archive.

Email and HTML are treated as untrusted data. Imported content is not executed as instructions.

## Running from Source

Requirements:

- Python 3.10 or newer
- SQLite with FTS5 support
- PySide6

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run WyrmMango:

```powershell
& ".\.venv\Scripts\python.exe" ".\src\app.py"
```

## Windows Release

The standalone Windows release contains:

```text
WyrmMango.exe
LICENSE
README.md
SHA256.txt
```

The packaged application stores its local database under:

```text
%LOCALAPPDATA%\WyrmMango\data\chatarchive.sqlite
```

`SHA256.txt` records the SHA-256 hash of the packaged executable so the release artifact can be checked before use.

## Project Structure

```text
WyrmMango/
├── assets/
│   ├── wyrmmango_icon.png
│   └── wyrmmango.ico
├── src/
│   ├── app.py
│   ├── database.py
│   ├── import_archive.py
│   ├── import_chatgpt.py
│   ├── import_claude.py
│   ├── import_gmail.py
│   └── search_archive.py
├── build_windows.ps1
├── prepare_windows_release.py
├── README.md
├── ROADMAP.md
├── requirements.txt
└── .gitignore
```

Local user data such as `data/`, imports, databases, backups, and generated exports are intentionally excluded from the public repository.

## Command-Line Search

Basic search:

```powershell
python .\src\search_archive.py "old project"
```

Exact phrase search:

```powershell
python .\src\search_archive.py "model registry" --exact
```

Show archive statistics:

```powershell
python .\src\search_archive.py --stats
```

## Local Database

WyrmMango uses a local SQLite database with FTS5 search support. The database is private local data and is not part of the public source repository.

## Version

Current application version: **0.2.0**

## Copyright

**Copyright © 2026 Celandra Dawson.**

This notice identifies the WyrmMango project copyright holder. Third-party components retain their own licenses and copyrights.

## License

WyrmMango is distributed under the **GNU General Public License v3.0**. See `LICENSE` for the complete license text.
