"""FTS5 query execution."""
from __future__ import annotations
import logging
import re
import sqlite3

from ..db.models import SearchResult
from ..db.catalog import get_file

logger = logging.getLogger(__name__)

FTS5_SPECIAL_CHARS = re.compile(r'[^a-zA-Z0-9\s\-_\'àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]')


def sanitize_fts_query(raw: str) -> str:
    """Prepare user input for FTS5 MATCH."""
    raw = raw.strip()
    if not raw:
        return ""
    # If user already wrote FTS5 operators, pass through with minimal sanitization
    if any(op in raw for op in (" AND ", " OR ", " NOT ", '"')):
        return raw
    # Wrap in quotes for phrase search if multi-word
    words = raw.split()
    if len(words) == 1:
        return words[0]
    # Use individual terms with implicit AND (FTS5 default)
    return " ".join(words)


def fts_search(
    search_conn: sqlite3.Connection,
    catalog_conn: sqlite3.Connection,
    fts_query: str,
    limit: int = 50,
) -> list[SearchResult]:
    query = sanitize_fts_query(fts_query)
    if not query:
        return []

    try:
        rows = search_conn.execute(
            """
            SELECT
                file_id,
                snippet(fts_files, 1, '<mark>', '</mark>', '...', 32) AS snippet,
                rank
            FROM fts_files
            WHERE fts_files MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
    except sqlite3.OperationalError as e:
        logger.warning("FTS query error for %r: %s", query, e)
        # Try again with quoted phrase
        try:
            safe = f'"{query}"'
            rows = search_conn.execute(
                """
                SELECT file_id,
                       snippet(fts_files, 1, '<mark>', '</mark>', '...', 32) AS snippet,
                       rank
                FROM fts_files WHERE fts_files MATCH ?
                ORDER BY rank LIMIT ?
                """,
                (safe, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []

    results = []
    for row in rows:
        file_id = row["file_id"]
        snippet = row["snippet"]
        record = get_file(catalog_conn, file_id)
        if not record:
            continue
        results.append(
            SearchResult(
                file_id=file_id,
                filename=record.filename,
                path=record.path,
                device_name=record.device_name,
                type_group=record.type_group,
                type_subgroup=record.type_subgroup,
                size=record.size,
                modified_at=record.modified_at,
                audio_metadata=record.audio_metadata,
                snippet=snippet,
            )
        )
    return results
