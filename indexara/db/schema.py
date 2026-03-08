"""SQL schema definitions."""

CATALOG_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    device_name TEXT NOT NULL,
    path TEXT NOT NULL,
    filename TEXT NOT NULL,
    extension TEXT,
    size INTEGER,
    created_at REAL,
    modified_at REAL,
    mime_type TEXT,
    type_group TEXT,
    type_subgroup TEXT,
    content_hash TEXT,
    last_indexed REAL,
    deleted INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_files_device ON files(device_name);
CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension);
CREATE INDEX IF NOT EXISTS idx_files_type_group ON files(type_group);
CREATE INDEX IF NOT EXISTS idx_files_modified ON files(modified_at);
CREATE INDEX IF NOT EXISTS idx_files_deleted ON files(deleted);

CREATE TABLE IF NOT EXISTS devices (
    hostname TEXT PRIMARY KEY,
    platform TEXT,
    last_seen REAL
);

CREATE TABLE IF NOT EXISTS steam_workshop (
    workshop_id TEXT PRIMARY KEY,
    resolved_name TEXT,
    game_name TEXT,
    description TEXT,
    last_resolved REAL
);

CREATE TABLE IF NOT EXISTS file_content (
    file_id TEXT PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
    text_content TEXT,
    extracted_at REAL
);

CREATE TABLE IF NOT EXISTS audio_metadata (
    file_id TEXT PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
    title TEXT,
    artist TEXT,
    album TEXT,
    album_artist TEXT,
    track_number INTEGER,
    disc_number INTEGER,
    year INTEGER,
    duration_seconds REAL,
    bitrate INTEGER,
    sample_rate INTEGER
);
"""

SEARCH_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE VIRTUAL TABLE IF NOT EXISTS fts_files USING fts5(
    file_id UNINDEXED,
    filename,
    path,
    artist,
    album,
    title,
    document_text,
    steam_workshop_name,
    tokenize = 'porter unicode61'
);
"""
