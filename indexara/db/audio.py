"""SQL queries for audio metadata insights and health checks."""
from __future__ import annotations
import sqlite3


def get_audio_health(conn: sqlite3.Connection, limit: int = 100) -> dict:
    """Detect common audio metadata problems."""
    # Summary counts in one pass
    summary_row = conn.execute(
        """
        SELECT
            COUNT(*) AS total_audio,
            SUM(CASE WHEN am.artist IS NULL OR am.artist = '' THEN 1 ELSE 0 END) AS missing_artist,
            SUM(CASE WHEN am.album  IS NULL OR am.album  = '' THEN 1 ELSE 0 END) AS missing_album,
            SUM(CASE WHEN am.title  IS NULL OR am.title  = '' THEN 1 ELSE 0 END) AS missing_title
        FROM files f
        LEFT JOIN audio_metadata am ON f.id = am.file_id
        WHERE f.type_group = 'audio' AND f.deleted = 0
        """
    ).fetchone()

    base = """
        SELECT f.path, f.filename
        FROM files f
        LEFT JOIN audio_metadata am ON f.id = am.file_id
        WHERE f.type_group = 'audio' AND f.deleted = 0
    """

    missing_artist = conn.execute(
        base + " AND (am.artist IS NULL OR am.artist = '') LIMIT ?", (limit,)
    ).fetchall()

    missing_album = conn.execute(
        base + " AND (am.album IS NULL OR am.album = '') LIMIT ?", (limit,)
    ).fetchall()

    missing_title = conn.execute(
        base + " AND (am.title IS NULL OR am.title = '') LIMIT ?", (limit,)
    ).fetchall()

    generic_titles = conn.execute(
        base + """
        AND am.title IS NOT NULL AND am.title != ''
        AND (
            am.title LIKE 'Track%'
            OR am.title LIKE 'Audio%'
            OR am.title LIKE 'Unknown%'
        )
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    return {
        "summary": dict(summary_row) if summary_row else {},
        "missing_artist": [dict(r) for r in missing_artist],
        "missing_album": [dict(r) for r in missing_album],
        "missing_title": [dict(r) for r in missing_title],
        "generic_titles": [dict(r) for r in generic_titles],
    }


def get_audio_cleanup(conn: sqlite3.Connection, limit: int = 50) -> dict:
    """Detect duplicate tracks and inconsistent artist naming."""
    hash_rows = conn.execute(
        """
        SELECT content_hash, COUNT(*) AS copies
        FROM files
        WHERE type_group = 'audio' AND deleted = 0 AND content_hash IS NOT NULL
        GROUP BY content_hash
        HAVING copies > 1
        ORDER BY copies DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    duplicate_tracks = []
    for row in hash_rows:
        paths = conn.execute(
            """
            SELECT path, filename FROM files
            WHERE content_hash = ? AND type_group = 'audio' AND deleted = 0
            LIMIT 5
            """,
            (row["content_hash"],),
        ).fetchall()
        duplicate_tracks.append({
            "content_hash": row["content_hash"],
            "copies": row["copies"],
            "paths": [dict(p) for p in paths],
        })

    artist_rows = conn.execute(
        """
        SELECT
            LOWER(am.artist) AS normalized,
            COUNT(DISTINCT am.artist) AS variants,
            GROUP_CONCAT(DISTINCT am.artist) AS artist_list
        FROM audio_metadata am
        JOIN files f ON f.id = am.file_id
        WHERE f.deleted = 0 AND am.artist IS NOT NULL AND am.artist != ''
        GROUP BY normalized
        HAVING variants > 1
        ORDER BY variants DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    return {
        "duplicate_tracks": duplicate_tracks,
        "inconsistent_artists": [dict(r) for r in artist_rows],
    }
