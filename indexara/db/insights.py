"""SQL queries powering the /insights endpoint.

All queries run against catalog.db using only the existing `files` table.
No filesystem access — purely derived from indexed metadata.
"""
from __future__ import annotations
import sqlite3


def get_largest_files(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """Return the biggest files by byte size."""
    rows = conn.execute(
        """
        SELECT path, filename, size, device_name
        FROM files
        WHERE deleted = 0
          AND size IS NOT NULL
        ORDER BY size DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_recent_files(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """Return the most recently created files."""
    rows = conn.execute(
        """
        SELECT path, filename, created_at, device_name
        FROM files
        WHERE deleted = 0
          AND created_at IS NOT NULL
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_duplicate_files(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """Find files with identical content hashes (true duplicates).

    Two passes:
    1. Find hashes that appear more than once.
    2. For each such hash, fetch up to 3 example paths so the user can
       see where the duplicates live without returning unbounded data.
    """
    # Step 1: find duplicate hashes and their copy count
    hash_rows = conn.execute(
        """
        SELECT content_hash, COUNT(*) AS copies, SUM(size) AS total_size
        FROM files
        WHERE deleted = 0
          AND content_hash IS NOT NULL
        GROUP BY content_hash
        HAVING copies > 1
        ORDER BY copies DESC, total_size DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    results = []
    for row in hash_rows:
        h = row["content_hash"]
        # Step 2: grab a sample of paths for this hash (cap at 5)
        paths = conn.execute(
            """
            SELECT path, filename, size, device_name
            FROM files
            WHERE deleted = 0
              AND content_hash = ?
            LIMIT 5
            """,
            (h,),
        ).fetchall()
        results.append({
            "content_hash": h,
            "copies": row["copies"],
            "wasted_bytes": row["total_size"] - (row["total_size"] // row["copies"]),
            "files": [dict(p) for p in paths],
        })
    return results


def get_disk_growth(conn: sqlite3.Connection, days: int = 7, limit: int = 20) -> dict:
    """Files newly indexed in the last N days, grouped by device + top new files."""
    import time
    cutoff = time.time() - (days * 86400)
    by_device = conn.execute(
        """
        SELECT device_name, COUNT(*) AS file_count, SUM(size) AS total_size
        FROM files
        WHERE deleted = 0
          AND last_indexed >= ?
        GROUP BY device_name
        ORDER BY total_size DESC
        """,
        (cutoff,),
    ).fetchall()
    top_files = conn.execute(
        """
        SELECT path, filename, size, device_name, last_indexed
        FROM files
        WHERE deleted = 0
          AND last_indexed >= ?
          AND size IS NOT NULL
        ORDER BY size DESC
        LIMIT ?
        """,
        (cutoff, limit),
    ).fetchall()
    return {
        "days": days,
        "by_device": [dict(r) for r in by_device],
        "top_new_files": [dict(r) for r in top_files],
    }


def get_cleanup_candidates(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """Large files (>100 MB) with no extension or tmp/temp/cache names."""
    rows = conn.execute(
        """
        SELECT path, filename, size, extension, device_name, type_group
        FROM files
        WHERE deleted = 0
          AND size > 104857600
          AND (
            extension IS NULL OR extension = ''
            OR lower(filename) LIKE 'tmp%'
            OR lower(filename) LIKE '%tmp'
            OR lower(filename) LIKE '%.tmp'
            OR lower(filename) LIKE '%temp%'
            OR lower(filename) LIKE '%cache%'
          )
        ORDER BY size DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_largest_folders(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """Aggregate file sizes by parent directory.

    The parent directory is derived by stripping the filename from the full
    path using SQLite string functions — no Python-side path processing needed.

    Example: path=/home/user/music/track.flac, filename=track.flac
             folder = /home/user/music
    """
    rows = conn.execute(
        """
        SELECT
            -- Trim trailing slash if filename is empty, handle root gracefully
            CASE
                WHEN length(path) = length(filename)
                    THEN '.'
                ELSE substr(path, 1, length(path) - length(filename) - 1)
            END AS folder,
            SUM(size)  AS total_size,
            COUNT(*)   AS file_count
        FROM files
        WHERE deleted = 0
          AND size IS NOT NULL
        GROUP BY folder
        ORDER BY total_size DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
