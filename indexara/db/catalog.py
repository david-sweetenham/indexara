"""CRUD operations for catalog.db."""
from __future__ import annotations
import sqlite3
import time
from .models import FileRecord, AudioMetadata, IndexBatch


def upsert_file(conn: sqlite3.Connection, record: FileRecord) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO files
          (id, device_name, path, filename, extension, size, created_at, modified_at,
           mime_type, type_group, type_subgroup, content_hash, last_indexed, deleted)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            record.id, record.device_name, record.path, record.filename,
            record.extension, record.size, record.created_at, record.modified_at,
            record.mime_type, record.type_group, record.type_subgroup,
            record.content_hash, record.last_indexed, int(record.deleted),
        ),
    )
    if record.audio_metadata:
        am = record.audio_metadata
        conn.execute(
            """
            INSERT OR REPLACE INTO audio_metadata
              (file_id, title, artist, album, album_artist, track_number,
               disc_number, year, duration_seconds, bitrate, sample_rate)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                record.id, am.title, am.artist, am.album, am.album_artist,
                am.track_number, am.disc_number, am.year, am.duration_seconds,
                am.bitrate, am.sample_rate,
            ),
        )
    if record.text_content:
        conn.execute(
            """
            INSERT OR REPLACE INTO file_content (file_id, text_content, extracted_at)
            VALUES (?,?,?)
            """,
            (record.id, record.text_content, time.time()),
        )


def upsert_batch(conn: sqlite3.Connection, batch: IndexBatch) -> None:
    upsert_device(conn, batch.device_name, batch.platform)
    with conn:
        for record in batch.records:
            upsert_file(conn, record)


def mark_deleted(conn: sqlite3.Connection, file_id: str) -> None:
    conn.execute("UPDATE files SET deleted=1 WHERE id=?", (file_id,))
    conn.commit()


def mark_missing_deleted(
    conn: sqlite3.Connection, device_name: str, seen_ids: set[str],
    roots: list | None = None,
) -> int:
    """Mark files as deleted if not in seen_ids, scoped to the given roots."""
    if roots:
        existing = set()
        for root in roots:
            rows = conn.execute(
                "SELECT id FROM files WHERE device_name=? AND deleted=0 AND path LIKE ?",
                (device_name, f"{root}%"),
            )
            existing.update(row[0] for row in rows)
    else:
        existing = {
            row[0]
            for row in conn.execute(
                "SELECT id FROM files WHERE device_name=? AND deleted=0", (device_name,)
            )
        }
    to_delete = existing - seen_ids
    if to_delete:
        placeholders = ",".join("?" * len(to_delete))
        conn.execute(
            f"UPDATE files SET deleted=1 WHERE id IN ({placeholders})",
            list(to_delete),
        )
        conn.commit()
    return len(to_delete)


def get_file(conn: sqlite3.Connection, file_id: str) -> FileRecord | None:
    row = conn.execute(
        "SELECT * FROM files WHERE id=? AND deleted=0", (file_id,)
    ).fetchone()
    if not row:
        return None
    return _row_to_record(conn, row)


def get_files_for_device(
    conn: sqlite3.Connection, device_name: str
) -> list[FileRecord]:
    rows = conn.execute(
        "SELECT * FROM files WHERE device_name=? AND deleted=0", (device_name,)
    ).fetchall()
    return [_row_to_record(conn, r) for r in rows]


def upsert_device(
    conn: sqlite3.Connection, hostname: str, platform: str
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO devices (hostname, platform, last_seen)
        VALUES (?,?,?)
        """,
        (hostname, platform, time.time()),
    )


def list_devices(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM devices ORDER BY last_seen DESC").fetchall()
    return [dict(r) for r in rows]


def get_steam_workshop(
    conn: sqlite3.Connection, workshop_id: str
) -> dict | None:
    row = conn.execute(
        "SELECT * FROM steam_workshop WHERE workshop_id=?", (workshop_id,)
    ).fetchone()
    return dict(row) if row else None


def upsert_steam_workshop(
    conn: sqlite3.Connection, workshop_id: str, data: dict
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO steam_workshop
          (workshop_id, resolved_name, game_name, description, last_resolved)
        VALUES (?,?,?,?,?)
        """,
        (
            workshop_id,
            data.get("resolved_name"),
            data.get("game_name"),
            data.get("description"),
            time.time(),
        ),
    )
    conn.commit()


def query_with_filters(
    conn: sqlite3.Connection, filters: dict, limit: int = 50
) -> list[FileRecord]:
    allowed_columns = {
        "device_name", "extension", "type_group", "type_subgroup",
        "mime_type", "filename", "deleted",
    }
    clauses = ["deleted=0"]
    params: list = []
    for key, val in filters.items():
        if key not in allowed_columns:
            continue
        if isinstance(val, list):
            placeholders = ",".join("?" * len(val))
            clauses.append(f"{key} IN ({placeholders})")
            params.extend(val)
        else:
            clauses.append(f"{key}=?")
            params.append(val)
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"SELECT * FROM files WHERE {where} LIMIT ?", params + [limit]
    ).fetchall()
    return [_row_to_record(conn, r) for r in rows]


def _row_to_record(conn: sqlite3.Connection, row: sqlite3.Row) -> FileRecord:
    d = dict(row)
    d["deleted"] = bool(d.get("deleted", 0))
    # Load audio metadata if present
    am_row = conn.execute(
        "SELECT * FROM audio_metadata WHERE file_id=?", (d["id"],)
    ).fetchone()
    if am_row:
        d["audio_metadata"] = AudioMetadata(**{
            k: v for k, v in dict(am_row).items() if k != "file_id"
        })
    return FileRecord(**d)
