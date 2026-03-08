"""GET /search and GET /ask endpoints."""
from __future__ import annotations
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Query

from ...db.models import AskResponse
from ...search import execute_search, execute_ask

logger = logging.getLogger(__name__)
router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=4)


@router.get("/search")
async def search_files(
    q: str = Query(..., description="Natural language search query"),
    limit: int = Query(50, ge=1, le=200),
):
    from ..app import get_connections
    cat_conn, srch_conn, config = get_connections()

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        _executor,
        lambda: execute_search(q, cat_conn, srch_conn, config, limit),
    )
    return {"results": [r.model_dump() for r in results], "query": q, "count": len(results)}


@router.get("/ask")
async def ask_files(
    q: str = Query(..., description="Natural language question about your files"),
):
    from ..app import get_connections
    cat_conn, srch_conn, config = get_connections()

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        _executor,
        lambda: execute_ask(q, cat_conn, srch_conn, config),
    )
    return response.model_dump()
