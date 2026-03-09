"""POST /scan/start, GET /scan/status, GET /scan/stats, GET /fs/browse — web-triggered indexing."""
from __future__ import annotations
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .auth import require_api_key

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Shared scan state ─────────────────────────────────────────────────────────
_lock = threading.Lock()
_status: dict[str, Any] = {
    "state": "idle",          # idle | running | done | error
    "paths": [],
    "files_indexed": 0,
    "files_skipped": 0,
    "files_errored": 0,
    "current_path": None,
    "started_at": None,
    "finished_at": None,
    "error": None,
}


class ScanRequest(BaseModel):
    paths: list[str]
    force: bool = False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/scan/start")
async def start_scan(req: ScanRequest, _: None = Depends(require_api_key)):
    from ..app import get_connections
    _, _, config = get_connections()

    with _lock:
        if _status["state"] == "running":
            raise HTTPException(status_code=409, detail="A scan is already running")
        paths = [str(Path(p).expanduser().resolve()) for p in req.paths]
        _status.update({
            "state": "running",
            "paths": paths,
            "files_indexed": 0,
            "files_skipped": 0,
            "files_errored": 0,
            "current_path": None,
            "started_at": time.time(),
            "finished_at": None,
            "error": None,
        })

    thread = threading.Thread(
        target=_run_scan,
        args=(paths, req.force, config),
        daemon=True,
    )
    thread.start()
    return {"started": True, "paths": paths}


@router.get("/scan/status")
async def scan_status():
    with _lock:
        return dict(_status)


@router.get("/scan/stats")
async def catalogue_stats():
    from ..app import get_connections
    cat_conn, _, _ = get_connections()

    total = cat_conn.execute("SELECT COUNT(*) FROM files WHERE deleted=0").fetchone()[0]
    by_type = cat_conn.execute(
        "SELECT type_group, COUNT(*) as cnt FROM files WHERE deleted=0 GROUP BY type_group ORDER BY cnt DESC"
    ).fetchall()
    total_size = cat_conn.execute(
        "SELECT COALESCE(SUM(size),0) FROM files WHERE deleted=0"
    ).fetchone()[0]
    last_indexed = cat_conn.execute(
        "SELECT MAX(last_indexed) FROM files WHERE deleted=0"
    ).fetchone()[0]

    return {
        "total_files": total,
        "total_size": total_size,
        "by_type": [{"type_group": r["type_group"] or "other", "count": r["cnt"]} for r in by_type],
        "last_indexed": last_indexed,
    }


@router.get("/fs/browse")
async def browse_filesystem(path: str = Query(default="/"), _: None = Depends(require_api_key)):
    """List subdirectories at a given path for the file-browser UI."""
    target = Path(path).expanduser().resolve()

    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail=f"Not a directory: {path}")

    try:
        entries = []
        for entry in sorted(target.iterdir(), key=lambda e: e.name.lower()):
            if entry.is_dir() and not entry.name.startswith('.'):
                try:
                    # Quick check we can at least stat it
                    entry.stat()
                    entries.append({"name": entry.name, "path": str(entry)})
                except PermissionError:
                    pass
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    # Build breadcrumbs from root to current path
    parts = target.parts  # ('/', 'home', 'david', ...)
    breadcrumbs = []
    for i, part in enumerate(parts):
        crumb_path = str(Path(*parts[: i + 1])) if i > 0 else "/"
        breadcrumbs.append({"name": part if part != "/" else "/", "path": crumb_path})

    return {
        "path": str(target),
        "parent": str(target.parent) if target != target.parent else None,
        "breadcrumbs": breadcrumbs,
        "entries": entries,
    }


# ── Background worker ─────────────────────────────────────────────────────────

def _run_scan(paths: list[str], force: bool, config):
    from ...db.connection import get_catalog_conn, get_search_conn
    from ...indexer.agent import run_indexer

    try:
        cat_conn = get_catalog_conn(config.catalog_db_path)
        srch_conn = get_search_conn(config.search_db_path)

        def on_progress(stats):
            with _lock:
                _status["files_indexed"] = stats.files_indexed
                _status["files_skipped"] = stats.files_skipped
                _status["files_errored"] = stats.files_errored

        run_indexer(
            [Path(p) for p in paths],
            config,
            force=force,
            progress_callback=on_progress,
        )

        with _lock:
            _status["state"] = "done"
            _status["finished_at"] = time.time()

    except Exception as exc:
        logger.exception("Scan failed: %s", exc)
        with _lock:
            _status["state"] = "error"
            _status["error"] = str(exc)
            _status["finished_at"] = time.time()
