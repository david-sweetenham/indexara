"""GET /devices endpoint."""
from __future__ import annotations
from fastapi import APIRouter
from ...db.catalog import list_devices

router = APIRouter()


@router.get("/devices")
async def list_known_devices():
    from ..app import get_connections
    cat_conn, _, _ = get_connections()
    return {"devices": list_devices(cat_conn)}
