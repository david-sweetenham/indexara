# Indexara

A cross-platform personal file catalogue with AI-powered natural language search.

Index files across multiple machines into a central SQLite catalogue. Search with natural language using your choice of AI backend.

## Features

- **Natural language search** — "FLAC albums by Radiohead", "Portishead flac files", "documents about taxes"
- **AI question answering** — "What documents mention broadband costs?"
- **Paginated results** — 25 results per page with Prev/Next controls at top and bottom
- **Web UI** — browser-based interface with Search, Ask, Insights, Scan, and Audio tabs
- **Quick filters** — one-click chips for Music, FLAC, MP3, Videos, Images, Documents, Large Files, Recent
- **Sortable results** — sort by relevance, name, size, date, or type
- **Open files** — Open or Open Folder buttons on every result card
- **Insights dashboard** — largest files, duplicates, top folders, disk growth, and cleanup candidates
- **Audio tab** — metadata health report (missing tags, generic titles), duplicate track detection, inconsistent artist names, inline tag editor
- **Web-triggered scans** — kick off indexing runs from the browser with live progress
- **File system browser** — browse your directory tree visually instead of typing paths
- **Multi-machine support** — index from any number of devices
- **Audio metadata** — artist, album, title extracted from FLAC, MP3, M4A, OGG, WAV
- **Document text extraction** — PDF, DOCX, TXT, Markdown indexed for full-text search
- **Steam Workshop detection** — resolves workshop item names
- **Smart exclusions** — `.indexignore` support (gitignore syntax) + built-in defaults
- **Local-first** — all data stored in SQLite, no cloud required

## Quick Start

### Prerequisites

- Python 3.11+
- An AI backend — one of:
  - [Anthropic API key](https://console.anthropic.com/) (cloud)
  - [Ollama](https://ollama.com/) running locally (free, no API key needed)
  - Any OpenAI-compatible endpoint (LM Studio, etc.)

### Install

```bash
git clone https://github.com/david-sweetenham/indexara.git
cd indexara
pip install -e .
```

### Configure

```bash
mkdir -p ~/.indexara
cp config/config.example.yaml ~/.indexara/config.yaml
# Edit ~/.indexara/config.yaml — set your paths and AI backend

# If using Anthropic (optional):
export ANTHROPIC_API_KEY=sk-ant-...
```

### Index your files

```bash
# Index a specific directory
indexara index ~/Documents ~/Music

# Or use paths from config
indexara index
```

### Search

```bash
indexara search "radiohead FLAC"
indexara search "PDF documents from 2023"
indexara ask "what documents mention project budgets?"
```

### Start the web UI

```bash
indexara serve
# Open http://localhost:8000
```

The web UI provides:
- **Search** — natural language search with quick filter chips, sortable results, and pagination
- **Ask** — AI-powered question answering over your file catalogue
- **Insights** — disk usage analysis: largest files, duplicates, folder sizes, disk growth, cleanup candidates
- **Scan** — browse your filesystem and kick off indexing runs with live progress
- **Audio** — metadata health dashboard and inline tag editor

## Single-machine mode (local)

The default mode. The indexer writes directly to `~/.indexara/catalog.db` and `~/.indexara/search.db`.

```yaml
# ~/.indexara/config.yaml
mode: local
paths:
  - ~/Documents
  - ~/Music
```

## Multi-machine mode (push)

Run the server on one machine, agents on others.

**Server machine:**
```bash
indexara serve
```

**Agent machines:**
```yaml
# ~/.indexara/config.yaml
mode: push
server_url: http://server-ip:8000
device_name: my-laptop
paths:
  - ~/Documents
```

```bash
indexara index
```

## Docker Compose

### Server only

```bash
# With Anthropic (optional):
ANTHROPIC_API_KEY=sk-ant-... docker compose up server

# With Ollama or local backend — no key needed:
docker compose up server
```

### With agent

```bash
# Edit docker/docker-compose.yml to set your mount paths
docker compose --profile agent up
```

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI |
| `/search?q=...` | GET | Natural language search |
| `/ask?q=...` | GET | AI question answering |
| `/index` | POST | Receive index batch (from agents) |
| `/devices` | GET | List indexed devices |
| `/insights` | GET | Disk usage insights (largest files, duplicates, folders) |
| `/scan/start` | POST | Start a background indexing scan |
| `/scan/status` | GET | Poll scan progress (state, files_indexed, files_skipped) |
| `/scan/stats` | GET | Catalogue summary (total files, size, breakdown by type) |
| `/fs/browse?path=` | GET | List subdirectories for the file browser UI |
| `/open?path=&action=` | GET | Open a file or folder in the desktop file manager |
| `/audio/health` | GET | Audio metadata health report (missing tags, generic titles) |
| `/audio/cleanup` | GET | Duplicate tracks and inconsistent artist name variants |
| `/audio/update_tags` | POST | Write audio tags (artist, album, title, year, track number) |

## File Type Support

| Type | Formats |
|------|---------|
| Audio | FLAC, ALAC, M4A, MP3, OGG, WAV, AIFF, Opus, WMA |
| Documents | PDF, DOCX, TXT, Markdown, RST, EPUB, ODT, RTF |
| Images | JPEG, PNG, GIF, WebP, TIFF, BMP, SVG, RAW |
| Video | MP4, MKV, AVI, MOV, WebM, FLV, WMV |
| Archives | ZIP, TAR, GZ, BZ2, XZ, 7Z, RAR, ZST |
| Code | Python, JS, TS, Rust, Go, Java, C/C++, and more |

## CLI Reference

```
indexara index [ROOTS...] [--push] [--force] [--config PATH]
indexara serve [--host HOST] [--port PORT] [--config PATH]
indexara search QUERY [--limit N] [--server] [--config PATH]
indexara ask QUESTION [--server] [--config PATH]
indexara insights [--limit N] [--server] [--config PATH]
indexara devices [--config PATH]
indexara rebuild-search
indexara audio health [--limit N] [--config PATH]
indexara audio duplicates [--limit N] [--config PATH]
indexara audio artists [--limit N] [--config PATH]
```

## .indexignore

Place `.indexignore` files in any directory to exclude files using gitignore syntax:

```gitignore
# Exclude large archives
*.iso
*.img

# Exclude specific folders
raw-footage/
backup-*/
```
