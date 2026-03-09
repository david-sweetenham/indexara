"""FastAPI application factory."""
from __future__ import annotations
import logging
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from ..config.schema import Config
from ..db.connection import get_catalog_conn, get_search_conn

logger = logging.getLogger(__name__)

# Thread-local connection storage — each worker thread gets its own SQLite connection.
# This avoids sharing a single connection object across threads (which is unsafe even
# with check_same_thread=False at the Python layer).
_tls = threading.local()
_catalog_db_path: str | None = None
_search_db_path: str | None = None
_config: Config | None = None


def get_connections():
    """Return (catalog_conn, search_conn, config) for the current thread.

    On first call per thread, opens a fresh SQLite connection so that each
    thread in the executor pool owns its own handle.
    """
    if not getattr(_tls, "initialized", False):
        _tls.catalog_conn = get_catalog_conn(_catalog_db_path)
        _tls.search_conn = get_search_conn(_search_db_path)
        _tls.initialized = True
    return _tls.catalog_conn, _tls.search_conn, _config


def create_app(config: Config) -> FastAPI:
    global _catalog_db_path, _search_db_path, _config
    _catalog_db_path = config.catalog_db_path
    _search_db_path = config.search_db_path
    _config = config

    app = FastAPI(
        title="Indexara",
        description="Personal file catalogue with AI-powered search",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def startup():
        # Initialise connections (and therefore schemas) for the event-loop thread.
        # Worker threads each initialise lazily on first request.
        get_connections()
        logger.info("Indexara server started. Catalog: %s", config.catalog_db_path)

    # Import and register routes
    from .routes.index import router as index_router
    from .routes.search import router as search_router
    from .routes.devices import router as devices_router
    from .routes.insights import router as insights_router
    from .routes.scan import router as scan_router
    from .routes.open import router as open_router
    from .routes.audio import router as audio_router

    app.include_router(index_router)
    app.include_router(search_router)
    app.include_router(devices_router)
    app.include_router(insights_router)
    app.include_router(scan_router)
    app.include_router(open_router)
    app.include_router(audio_router)

    # Serve web UI
    web_dir = Path(__file__).parent.parent / "web"
    if web_dir.exists():
        app.mount("/web", StaticFiles(directory=str(web_dir)), name="web")

        @app.get("/")
        async def serve_ui():
            return FileResponse(str(web_dir / "index.html"))

    return app
