"""Unified search executor combining FTS and metadata filters."""
from __future__ import annotations
import logging
import sqlite3

from ..db.models import QueryInterpretation, SearchResult, AskResponse
from ..db.catalog import query_with_filters, get_file
from .fts import fts_search
from .claude_search import interpret_query, synthesize_answer

logger = logging.getLogger(__name__)


def execute_search(
    query: str,
    catalog_conn: sqlite3.Connection,
    search_conn: sqlite3.Connection,
    anthropic_client,
    limit: int = 50,
) -> list[SearchResult]:
    """Run a natural language search and return ranked results."""
    interpretation = interpret_query(query, anthropic_client)
    logger.debug("Query interpretation: %s", interpretation)
    return _execute_interpreted(interpretation, catalog_conn, search_conn)


def execute_interpreted_search(
    interpretation: QueryInterpretation,
    catalog_conn: sqlite3.Connection,
    search_conn: sqlite3.Connection,
) -> list[SearchResult]:
    return _execute_interpreted(interpretation, catalog_conn, search_conn)


def _execute_interpreted(
    interp: QueryInterpretation,
    catalog_conn: sqlite3.Connection,
    search_conn: sqlite3.Connection,
) -> list[SearchResult]:
    limit = interp.limit
    fts_results: list[SearchResult] = []
    filter_results: list[SearchResult] = []

    if interp.fts_query:
        fts_results = fts_search(search_conn, catalog_conn, interp.fts_query, limit * 2)

    if interp.filters:
        filter_records = query_with_filters(catalog_conn, interp.filters, limit * 2)
        filter_ids = {r.id for r in filter_records}
    else:
        filter_ids = None

    if interp.fts_query and interp.filters:
        # Intersect: keep FTS results that also pass the filters
        results = [r for r in fts_results if r.file_id in filter_ids]
    elif interp.fts_query:
        results = fts_results
    elif interp.filters:
        filter_records = query_with_filters(catalog_conn, interp.filters, limit)
        results = [
            SearchResult(
                file_id=r.id,
                filename=r.filename,
                path=r.path,
                device_name=r.device_name,
                type_group=r.type_group,
                type_subgroup=r.type_subgroup,
                size=r.size,
                modified_at=r.modified_at,
                audio_metadata=r.audio_metadata,
            )
            for r in filter_records
        ]
    else:
        return []

    return results[:limit]


def execute_ask(
    question: str,
    catalog_conn: sqlite3.Connection,
    search_conn: sqlite3.Connection,
    anthropic_client,
) -> AskResponse:
    """Answer a question using file content as context."""
    results = execute_search(question, catalog_conn, search_conn, anthropic_client, limit=10)

    # Fetch text content for top results
    content_snippets: list[tuple[str, str]] = []
    for result in results[:10]:
        row = catalog_conn.execute(
            "SELECT text_content FROM file_content WHERE file_id=?",
            (result.file_id,),
        ).fetchone()
        if row and row["text_content"]:
            content_snippets.append((result.filename, row["text_content"][:500]))
        else:
            content_snippets.append((result.filename, result.snippet or ""))

    answer = synthesize_answer(question, results, content_snippets, anthropic_client)
    return AskResponse(answer=answer, sources=results[:5])
