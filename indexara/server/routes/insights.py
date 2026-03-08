"""GET /insights — disk usage analytics derived from the catalogue."""
from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter

from ...db.insights import (
    get_largest_files,
    get_recent_files,
    get_duplicate_files,
    get_largest_folders,
)

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=2)


@router.get("/insights")
async def get_insights(limit: int = 20):
    """Return disk-usage insights derived purely from indexed metadata.

    All four sections are computed in a single thread-pool call to avoid
    multiple round-trips to the event loop while keeping SQLite off it.
    """
    from ..app import get_connections
    cat_conn, _, _ = get_connections()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(
        _executor, lambda: _run_queries(cat_conn, limit)
    )
    return data


def _run_queries(cat_conn, limit: int) -> dict:
    return {
        "largest_files":  get_largest_files(cat_conn, limit),
        "recent_files":   get_recent_files(cat_conn, limit),
        "duplicate_files": get_duplicate_files(cat_conn, limit),
        "largest_folders": get_largest_folders(cat_conn, limit),
    }
