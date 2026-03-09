"""POST /index — receive batch updates from indexer agents."""
from __future__ import annotations
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from ...db.models import IndexBatch
from ...db import upsert_batch, index_batch

logger = logging.getLogger(__name__)
router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=4)


class MarkDeletedRequest(BaseModel):
    device_name: str
    seen_ids: list[str]
    roots: list[str]


@router.post("/index")
async def receive_index_batch(
    batch: IndexBatch,
    catalog_conn=Depends(lambda: None),
    search_conn=Depends(lambda: None),
    x_api_key: str | None = Header(default=None),
    _deps=Depends(lambda: None),
):
    # Dependencies injected via app state — see app.py for actual wiring
    from ..app import get_connections
    cat_conn, srch_conn, config = get_connections()

    if config.api_key and x_api_key != config.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        _executor, lambda: _do_index(batch, cat_conn, srch_conn)
    )
    return {"indexed": len(batch.records), "device": batch.device_name}


def _do_index(batch, cat_conn, srch_conn):
    upsert_batch(cat_conn, batch)
    cat_conn.commit()
    index_batch(srch_conn, batch.records)
    srch_conn.commit()


@router.post("/index/mark_deleted")
async def mark_deleted_endpoint(
    req: MarkDeletedRequest,
    x_api_key: str | None = Header(default=None),
):
    """Mark files no longer present on an agent device as deleted."""
    from ..app import get_connections
    cat_conn, srch_conn, config = get_connections()

    if config.api_key and x_api_key != config.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    loop = asyncio.get_event_loop()
    count = await loop.run_in_executor(
        _executor, lambda: _do_mark_deleted(req, cat_conn, srch_conn)
    )
    return {"deleted": count, "device": req.device_name}


def _do_mark_deleted(req: MarkDeletedRequest, cat_conn, srch_conn) -> int:
    from ...db.catalog import mark_missing_deleted
    from ...db.search_index import _delete_from_index
    deleted_ids = mark_missing_deleted(
        cat_conn, req.device_name, set(req.seen_ids), roots=req.roots,
    )
    if deleted_ids and srch_conn:
        with srch_conn:
            for fid in deleted_ids:
                _delete_from_index(srch_conn, fid)
    return len(deleted_ids)
