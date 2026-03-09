"""FastAPI application factory."""
from __future__ import annotations
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from ..config.schema import Config
from ..db.connection import get_catalog_conn, get_search_conn

logger = logging.getLogger(__name__)

# Module-level connection storage (initialized at startup)
_catalog_conn = None
_search_conn = None
_config: Config | None = None


def get_connections():
    return _catalog_conn, _search_conn, _config


def create_app(config: Config) -> FastAPI:
    global _catalog_conn, _search_conn, _config
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
        global _catalog_conn, _search_conn
        _catalog_conn = get_catalog_conn(config.catalog_db_path)
        _search_conn = get_search_conn(config.search_db_path)
        logger.info("Indexara server started. Catalog: %s", config.catalog_db_path)

    @app.on_event("shutdown")
    async def shutdown():
        if _catalog_conn:
            _catalog_conn.close()
        if _search_conn:
            _search_conn.close()

    # Import and register routes
    from .routes.index import router as index_router
    from .routes.search import router as search_router
    from .routes.devices import router as devices_router
    from .routes.insights import router as insights_router
    from .routes.scan import router as scan_router
    from .routes.open import router as open_router

    app.include_router(index_router)
    app.include_router(search_router)
    app.include_router(devices_router)
    app.include_router(insights_router)
    app.include_router(scan_router)
    app.include_router(open_router)

    # Serve web UI
    web_dir = Path(__file__).parent.parent / "web"
    if web_dir.exists():
        app.mount("/web", StaticFiles(directory=str(web_dir)), name="web")

        @app.get("/")
        async def serve_ui():
            return FileResponse(str(web_dir / "index.html"))

    return app
