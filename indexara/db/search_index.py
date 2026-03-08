"""FTS5 write operations for search.db."""
from __future__ import annotations
import sqlite3
from .models import FileRecord


def index_file(search_conn: sqlite3.Connection, record: FileRecord) -> None:
    _delete_from_index(search_conn, record.id)
    am = record.audio_metadata
    search_conn.execute(
        """
        INSERT INTO fts_files
          (file_id, filename, path, artist, album, title, document_text, steam_workshop_name)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            record.id,
            record.filename,
            record.path,
            am.artist if am else None,
            am.album if am else None,
            am.title if am else None,
            record.text_content,
            record.steam_workshop_name,
        ),
    )


def index_batch(
    search_conn: sqlite3.Connection, records: list[FileRecord]
) -> None:
    with search_conn:
        for record in records:
            if not record.deleted:
                index_file(search_conn, record)
            else:
                _delete_from_index(search_conn, record.id)


def _delete_from_index(search_conn: sqlite3.Connection, file_id: str) -> None:
    search_conn.execute(
        "DELETE FROM fts_files WHERE file_id=?", (file_id,)
    )


def rebuild_index(
    catalog_conn: sqlite3.Connection, search_conn: sqlite3.Connection
) -> int:
    """Rebuild search index from catalog. Returns count of indexed files."""
    search_conn.execute("DELETE FROM fts_files")
    search_conn.commit()
    batch_size = 500
    offset = 0
    total = 0
    while True:
        rows = catalog_conn.execute(
            "SELECT id FROM files WHERE deleted=0 LIMIT ? OFFSET ?",
            (batch_size, offset),
        ).fetchall()
        if not rows:
            break
        from .catalog import get_file
        with search_conn:
            for row in rows:
                record = get_file(catalog_conn, row["id"])
                if record:
                    index_file(search_conn, record)
                    total += 1
        offset += batch_size
    return total
