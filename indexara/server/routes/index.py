"""POST /index — receive batch updates from indexer agents."""
from __future__ import annotations
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Header

from ...db.models import IndexBatch
from ...db import upsert_batch, index_batch

logger = logging.getLogger(__name__)
router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=4)


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
