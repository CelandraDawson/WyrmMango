# WyrmMango

**Dig deep. Find the thread.**

WyrmMango is a private, local-first desktop application for importing and searching your own ChatGPT conversation history.

Your archive stays on your computer. WyrmMango builds a local SQLite search database so you can rediscover projects, ideas, code, decisions, and forgotten conversations without uploading your history to another service.

## Features

- Import an official ChatGPT data export ZIP
- Automatically discover numbered conversation JSON files
- Preserve conversation and message data locally
- SQLite FTS5 full-text search
- Exact phrase search
- Filter by message role, conversation title, and date range
- Read matched messages and full conversations
- Export search results and conversations to Markdown
- Re-import updated ChatGPT exports
- Local desktop interface built with PySide6

## Privacy

WyrmMango is designed around local ownership of personal conversation history.

The public source repository does **not** contain your ChatGPT conversations.

The following are excluded from Git by default:

- ChatGPT export ZIP files
- conversation JSON files
- SQLite databases
- attachments
- local archive directories
- local environment files
- Python virtual environments
- backup files

Never commit your personal ChatGPT export or generated SQLite database to a public repository.

## Requirements

- Python 3.10 or newer
- SQLite with FTS5 support
- PySide6

Install dependencies with:

```powershell
python -m pip install -r requirements.txt
```

## Running WyrmMango

From the project directory:

```powershell
& ".\.venv\Scripts\python.exe" ".\src\app.py"
```

## Project Structure

```text
WyrmMango/
├── assets/
│   ├── wyrmmango_icon.png
│   └── wyrmmango.ico
├── src/
│   ├── app.py
│   ├── database.py
│   ├── import_chatgpt.py
│   └── search_archive.py
├── README.md
├── ROADMAP.md
├── requirements.txt
└── .gitignore
```

Local user data such as `data/` and `exports/` is intentionally excluded from the public repository.

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

The local SQLite archive is deliberately ignored by Git and is not part of the WyrmMango source repository.

## Version

Current application version: **0.1.0**

## License

A license has not yet been selected.
