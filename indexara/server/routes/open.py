"""GET /open — open a file or its containing folder in the desktop file manager."""
from __future__ import annotations
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from .auth import require_api_key

router = APIRouter()


@router.get("/open")
async def open_path(
    path: str = Query(..., description="Absolute path to open"),
    action: str = Query("file", description="'file' to open the file, 'folder' to open its parent"),
    _: None = Depends(require_api_key),
):
    """Fire xdg-open for the given path. Non-blocking — returns immediately."""
    p = Path(path)
    target = p.parent if action == "folder" else p

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {target}")

    try:
        subprocess.Popen(
            ["xdg-open", str(target)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="xdg-open not available on this system")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "ok", "path": str(target)}
